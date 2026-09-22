"""
Safe database operations with error handling and retry logic.

This module wraps Supabase operations with proper error handling,
retry logic for transient failures, and consistent error messages.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from app.core.retry import DATABASE_RETRY, retry_with_backoff
from app.models.errors import DatabaseError, ResourceNotFoundError

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Common transient database errors that should be retried
TRANSIENT_DB_ERRORS = (
    ConnectionError,
    TimeoutError,
    # Add Supabase-specific transient errors here
)


def safe_db_operation(operation_name: str):
    """
    Decorator that wraps database operations with error handling and retry logic.
    
    Args:
        operation_name: Name of the operation (for logging and error messages)
        
    Example:
        @safe_db_operation("fetch_user")
        def get_user(user_id: str):
            return supabase.table("users").select("*").eq("id", user_id).execute()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                # Apply retry logic for transient errors
                result = retry_with_backoff(
                    max_attempts=DATABASE_RETRY.max_attempts,
                    base_delay=DATABASE_RETRY.base_delay,
                    max_delay=DATABASE_RETRY.max_delay,
                    exceptions=TRANSIENT_DB_ERRORS
                )(func)(*args, **kwargs)
                
                return result
                
            except TRANSIENT_DB_ERRORS as exc:
                # Transient error that couldn't be resolved after retries
                logger.error(
                    f"Database operation '{operation_name}' failed after retries: {exc}",
                    exc_info=True
                )
                raise DatabaseError(
                    message=f"Database temporarily unavailable: {exc!s}",
                    operation=operation_name,
                    is_retryable=True,
                    details={"error_type": type(exc).__name__}
                )
                
            except Exception as exc:
                # Non-transient error
                logger.error(
                    f"Database operation '{operation_name}' failed: {exc}",
                    exc_info=True
                )
                raise DatabaseError(
                    message=str(exc),
                    operation=operation_name,
                    is_retryable=False,
                    details={"error_type": type(exc).__name__}
                )
        
        return wrapper  # type: ignore
    
    return decorator


@safe_db_operation("insert")
def safe_insert(supabase_client: Any, table: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Safely insert a record into a table.
    
    Args:
        supabase_client: Supabase client instance
        table: Table name
        data: Data to insert
        
    Returns:
        Inserted record
        
    Raises:
        DatabaseError: If insert fails
    """
    try:
        result = supabase_client.table(table).insert(data).execute()
        
        if not result.data:
            raise DatabaseError(
                message="Insert operation returned no data",
                operation="insert",
                is_retryable=False,
                details={"table": table}
            )
        
        return result.data[0]
        
    except Exception as exc:
        logger.error(f"Failed to insert into {table}: {exc}", exc_info=True)
        raise


@safe_db_operation("upsert")
def safe_upsert(supabase_client: Any, table: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Safely upsert a record into a table.
    
    Args:
        supabase_client: Supabase client instance
        table: Table name
        data: Data to upsert
        
    Returns:
        Upserted record
        
    Raises:
        DatabaseError: If upsert fails
    """
    try:
        result = supabase_client.table(table).upsert(data).execute()
        
        if not result.data:
            raise DatabaseError(
                message="Upsert operation returned no data",
                operation="upsert",
                is_retryable=False,
                details={"table": table}
            )
        
        return result.data[0]
        
    except Exception as exc:
        logger.error(f"Failed to upsert into {table}: {exc}", exc_info=True)
        raise


@safe_db_operation("select")
def safe_select(
    supabase_client: Any,
    table: str,
    columns: str = "*",
    filters: dict[str, Any] | None = None,
    limit: int | None = None
) -> list[dict[str, Any]]:
    """
    Safely select records from a table.
    
    Args:
        supabase_client: Supabase client instance
        table: Table name
        columns: Columns to select (default: "*")
        filters: Dictionary of field: value filters
        limit: Maximum number of records to return
        
    Returns:
        List of records
        
    Raises:
        DatabaseError: If select fails
    """
    try:
        query = supabase_client.table(table).select(columns)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                query = query.eq(field, value)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        result = query.execute()
        return result.data or []
        
    except Exception as exc:
        logger.error(f"Failed to select from {table}: {exc}", exc_info=True)
        raise


@safe_db_operation("select_single")
def safe_select_single(
    supabase_client: Any,
    table: str,
    filters: dict[str, Any],
    columns: str = "*",
    required: bool = False
) -> dict[str, Any] | None:
    """
    Safely select a single record from a table.
    
    Args:
        supabase_client: Supabase client instance
        table: Table name
        filters: Dictionary of field: value filters
        columns: Columns to select (default: "*")
        required: If True, raise ResourceNotFoundError if not found
        
    Returns:
        Single record or None if not found
        
    Raises:
        DatabaseError: If select fails
        ResourceNotFoundError: If required=True and not found
    """
    try:
        query = supabase_client.table(table).select(columns)
        
        # Apply filters
        for field, value in filters.items():
            query = query.eq(field, value)
        
        result = query.maybe_single().execute()
        
        if required and not result.data:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
            raise ResourceNotFoundError(
                resource=table,
                resource_id=filter_str
            )
        
        return result.data
        
    except ResourceNotFoundError:
        raise
    except Exception as exc:
        logger.error(f"Failed to select single from {table}: {exc}", exc_info=True)
        raise


@safe_db_operation("update")
def safe_update(
    supabase_client: Any,
    table: str,
    filters: dict[str, Any],
    updates: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Safely update records in a table.
    
    Args:
        supabase_client: Supabase client instance
        table: Table name
        filters: Dictionary of field: value filters
        updates: Dictionary of fields to update
        
    Returns:
        List of updated records
        
    Raises:
        DatabaseError: If update fails
    """
    try:
        query = supabase_client.table(table).update(updates)
        
        # Apply filters
        for field, value in filters.items():
            query = query.eq(field, value)
        
        result = query.execute()
        return result.data or []
        
    except Exception as exc:
        logger.error(f"Failed to update {table}: {exc}", exc_info=True)
        raise


@safe_db_operation("delete")
def safe_delete(
    supabase_client: Any,
    table: str,
    filters: dict[str, Any]
) -> int:
    """
    Safely delete records from a table.
    
    Args:
        supabase_client: Supabase client instance
        table: Table name
        filters: Dictionary of field: value filters
        
    Returns:
        Number of deleted records
        
    Raises:
        DatabaseError: If delete fails
    """
    try:
        query = supabase_client.table(table).delete()
        
        # Apply filters
        for field, value in filters.items():
            query = query.eq(field, value)
        
        result = query.execute()
        return len(result.data) if result.data else 0
        
    except Exception as exc:
        logger.error(f"Failed to delete from {table}: {exc}", exc_info=True)
        raise


def safe_batch_insert(
    supabase_client: Any,
    table: str,
    records: list[dict[str, Any]],
    batch_size: int = 100
) -> int:
    """
    Safely insert multiple records in batches.
    
    Args:
        supabase_client: Supabase client instance
        table: Table name
        records: List of records to insert
        batch_size: Number of records per batch
        
    Returns:
        Total number of records inserted
        
    Raises:
        DatabaseError: If batch insert fails
    """
    total_inserted = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        
        try:
            result = supabase_client.table(table).insert(batch).execute()
            total_inserted += len(result.data) if result.data else 0
            
            logger.debug(
                f"Inserted batch {i // batch_size + 1}: {len(batch)} records into {table}"
            )
            
        except Exception as exc:
            logger.error(
                f"Failed to insert batch {i // batch_size + 1} into {table}: {exc}",
                exc_info=True
            )
            raise DatabaseError(
                message=f"Batch insert failed: {exc!s}",
                operation="batch_insert",
                is_retryable=False,
                details={
                    "table": table,
                    "batch_number": i // batch_size + 1,
                    "batch_size": len(batch)
                }
            )
    
    logger.info(f"Successfully inserted {total_inserted} records into {table}")
    return total_inserted
