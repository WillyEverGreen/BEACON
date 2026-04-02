
import logging
logger = logging.getLogger(__name__)

def aggregate_issues(issues: list[dict]) -> tuple[list[dict], dict]:
    if not issues:
        return [], {'original_count': 0, 'aggregated_count': 0, 'compression_ratio': 0.0}
        
    aggregated = {}
    
    for issue in issues:
        rid = issue.get('rule_id', 'unknown')
        
        if rid not in aggregated:
            aggregated[rid] = {
                'rule_id': rid,
                'rule_type': issue.get('rule_type', 'unknown'),
                'severity': issue.get('severity', 'minor'),
                'domain': issue.get('domain', 'general'),
                'message': issue.get('message', ''),
                'affected_count': 0,
                'sample_nodes': [],
                'confidence': issue.get('confidence', 0.0),
                'confidence_reason': issue.get('confidence_reason', ''),
                'fix_effort': issue.get('fix_effort', 'medium'),
            }
            if 'impact_summary' in issue:
                aggregated[rid]['impact_summary'] = issue['impact_summary']
            
        agg = aggregated[rid]
        agg['affected_count'] += 1
        
        if issue.get('confidence', 0.0) > agg['confidence']:
            agg['confidence'] = issue['confidence']
            if 'confidence_reason' in issue:
                agg['confidence_reason'] = issue['confidence_reason']
            
        if len(agg['sample_nodes']) < 5:
            node_info = {}
            if 'html_snippet' in issue and issue['html_snippet']:
                node_info['html'] = issue['html_snippet']
            if 'selector' in issue and issue['selector']:
                node_info['selector'] = issue['selector']
            if 'evidence' in issue and issue['evidence']:
                node_info['evidence'] = issue['evidence']
                
            if node_info and node_info not in agg['sample_nodes']:
                agg['sample_nodes'].append(node_info)
                
    agg_list = list(aggregated.values())
    original = len(issues)
    final_count = len(agg_list)
    ratio = round((original - final_count) / original * 100, 1) if original else 0.0
    
    telemetry = {
        'original_count': original,
        'aggregated_count': final_count,
        'compression_ratio': ratio
    }
    
    return agg_list, telemetry
