
import logging

logger = logging.getLogger(__name__)

def aggregate_issues(issues: list[dict]) -> tuple[list[dict], dict]:
    if not issues:
        return [], {'original_count': 0, 'aggregated_count': 0, 'compression_ratio': 0.0}
        
    aggregated = {}
    
    for issue in issues:
        rid = issue.get('rule_id', 'unknown')
        
        if rid not in aggregated:
            wcag_crit = issue.get('wcag_criterion') or issue.get('wcag_sc') or ''
            wcag_lvl = issue.get('wcag_level') or 'AA'
            wcag_dict = issue.get('wcag') if isinstance(issue.get('wcag'), dict) else ({'criterion': wcag_crit, 'level': wcag_lvl} if wcag_crit else {})
            issue_id = issue.get('id') or issue.get('issue_id') or issue.get('finding_id') or f"agg-{rid}"

            aggregated[rid] = {
                'id': issue_id,
                'issue_id': issue_id,
                'finding_id': issue_id,
                'rule_id': rid,
                'raw_rule_id': issue.get('raw_rule_id', rid),
                'rule_type': issue.get('rule_type', 'unknown'),
                'severity': issue.get('severity', 'minor'),
                'domain': issue.get('domain', 'general'),
                'category': issue.get('category') or 'General',
                'wcag_criterion': wcag_crit,
                'wcag_level': wcag_lvl,
                'wcag': wcag_dict,
                'message': issue.get('message', ''),
                'description': issue.get('description') or issue.get('message', ''),
                'suggested_fix': issue.get('suggested_fix') or issue.get('recommendation') or issue.get('fix_recommendation') or '',
                'selector': issue.get('selector') or issue.get('element') or '',
                'element': issue.get('element') or issue.get('selector') or '',
                'html': issue.get('html') or issue.get('html_snippet') or '',
                'html_snippet': issue.get('html_snippet') or issue.get('html') or '',
                'affected_count': 0,
                'sample_nodes': [],
                'confidence': issue.get('confidence', 0.0),
                'confidence_reason': issue.get('confidence_reason', ''),
                'fix_effort': issue.get('fix_effort', 'medium'),
                'source_engine': issue.get('source_engine') or issue.get('engine', 'scanner'),
                'engine': issue.get('engine') or issue.get('source_engine', 'scanner'),
                'verification_result': issue.get('verification_result', 'needs_review'),
                'needs_manual_review': issue.get('needs_manual_review', False),
                'help_url': issue.get('help_url', ''),
            }
            if 'impact_summary' in issue:
                aggregated[rid]['impact_summary'] = issue['impact_summary']
            if 'disability_impact' in issue:
                aggregated[rid]['disability_impact'] = issue['disability_impact']
            if 'persona_impact' in issue:
                aggregated[rid]['persona_impact'] = issue['persona_impact']
            if 'enrichment' in issue:
                aggregated[rid]['enrichment'] = issue['enrichment']
            if 'adjudication' in issue:
                aggregated[rid]['adjudication'] = issue['adjudication']
            
        agg = aggregated[rid]
        agg['affected_count'] += 1
        
        # Populate selector/html snippet if initial issue lacked it
        if not agg.get('selector') and (issue.get('selector') or issue.get('element')):
            sel = issue.get('selector') or issue.get('element')
            agg['selector'] = sel
            agg['element'] = sel
        if not agg.get('html_snippet') and (issue.get('html_snippet') or issue.get('html')):
            html = issue.get('html_snippet') or issue.get('html')
            agg['html_snippet'] = html
            agg['html'] = html
        if not agg.get('wcag_criterion') and (issue.get('wcag_criterion') or issue.get('wcag_sc')):
            agg['wcag_criterion'] = issue.get('wcag_criterion') or issue.get('wcag_sc')
            agg['wcag_level'] = issue.get('wcag_level') or 'AA'
            agg['wcag'] = {'criterion': agg['wcag_criterion'], 'level': agg['wcag_level']}
        if (not agg.get('category') or agg.get('category') == 'General') and issue.get('category') and issue.get('category') != 'General':
            agg['category'] = issue['category']

        if issue.get('verification_result') == 'verified_failure':
            agg['verification_result'] = 'verified_failure'

        if issue.get('confidence', 0.0) > agg['confidence']:
            agg['confidence'] = issue['confidence']
            if 'confidence_reason' in issue:
                agg['confidence_reason'] = issue['confidence_reason']
            
        if len(agg['sample_nodes']) < 5:
            node_info = {}
            if issue.get('html_snippet') or issue.get('html'):
                node_info['html'] = issue.get('html_snippet') or issue.get('html')
            if issue.get('selector') or issue.get('element'):
                node_info['selector'] = issue.get('selector') or issue.get('element')
            if issue.get('evidence'):
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

