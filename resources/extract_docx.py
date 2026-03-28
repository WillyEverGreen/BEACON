from docx import Document
from lxml import etree

doc = Document(r'd:\HACKATHON\DJ HACK\resources\Accessibility_Resource_Master_List.docx')

# Get all hyperlinks from rels
rels = doc.part.rels
link_map = {}
for rel_id, rel in rels.items():
    if 'hyperlink' in str(rel.reltype):
        link_map[rel_id] = rel.target_ref

ns_r = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
ns_w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

output = []

# Process paragraphs + tables in document order
body = doc.element.body

for child in body:
    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
    
    if tag == 'p':
        # Paragraph
        text_parts = []
        for elem in child.iter():
            if elem.tag == ns_w + 't' and elem.text:
                text_parts.append(elem.text)
        text = ''.join(text_parts).strip()
        
        # Find hyperlinks
        hyperlinks = child.findall(f'.//{ns_w.replace("main","main")}hyperlink'.replace(ns_w, '').replace('{', '').replace('}', ''))
        links_in_para = []
        for hl in child:
            if hl.tag.endswith('hyperlink'):
                rid = hl.get(ns_r + 'id')
                if rid and rid in link_map:
                    hl_text = ''.join(t.text or '' for t in hl.iter() if t.tag == ns_w + 't')
                    links_in_para.append(f'[{hl_text}]({link_map[rid]})')
        
        if links_in_para:
            output.append(f'{text}')
            for link in links_in_para:
                output.append(f'  LINK: {link}')
        elif text:
            output.append(text)
    
    elif tag == 'tbl':
        output.append('\n--- TABLE ---')
        # Find the table object
        for table in doc.tables:
            if table._element is child:
                for row in table.rows:
                    row_parts = []
                    for cell in row.cells:
                        cell_text = cell.text.strip().replace('\n', ' | ')
                        
                        # Find links in cell
                        cell_links = []
                        for hl in cell._element.iter():
                            if hl.tag.endswith('hyperlink'):
                                rid = hl.get(ns_r + 'id')
                                if rid and rid in link_map:
                                    hl_text = ''.join(t.text or '' for t in hl.iter() if t.tag == ns_w + 't')
                                    cell_links.append(f'[{hl_text}]({link_map[rid]})')
                        
                        if cell_links:
                            row_parts.append(f'{cell_text} {" ".join(cell_links)}')
                        else:
                            row_parts.append(cell_text)
                    output.append(' || '.join(row_parts))
                break
        output.append('--- END TABLE ---\n')

with open(r'd:\HACKATHON\DJ HACK\resources\docx_extracted.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("Done! Written to resources/docx_extracted.txt")
