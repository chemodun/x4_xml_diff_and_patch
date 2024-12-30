import argparse
import os
import sys
import logging
from lxml import etree
import re

def get_input(prompt):
    return input(prompt)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Generate XML diff between two XML files or directories.')
    parser.add_argument('original_xml', nargs='?', help='Path to the original XML file or directory')
    parser.add_argument('modified_xml', nargs='?', help='Path to the modified XML file or directory')
    parser.add_argument('diff_xml', nargs='?', help='Path for the output diff XML file or directory')
    parser.add_argument('--xsd', dest='diff_xsd', help='Path to the diff.xsd schema file', default=None)
    args = parser.parse_args()

    if not args.original_xml:
        args.original_xml = get_input('Enter path to original XML file or directory: ').strip()
    if not args.modified_xml:
        args.modified_xml = get_input('Enter path to modified XML file or directory: ').strip()
    if not args.diff_xml:
        args.diff_xml = get_input('Enter path for diff XML file or directory: ').strip()

    # Convert to absolute paths
    args.original_xml = os.path.abspath(args.original_xml)
    args.modified_xml = os.path.abspath(args.modified_xml)
    args.diff_xml = os.path.abspath(args.diff_xml)
    args.diff_xsd = os.path.abspath(args.diff_xsd) if args.diff_xsd else None

    return args.original_xml, args.modified_xml, args.diff_xml, args.diff_xsd

def detect_indentation(xml_path):
    """
    Detects the per-level indentation used in the given XML file.

    Args:
        xml_path (str): Path to the XML file.

    Returns:
        str: The per-level indentation string (e.g., '    ' for four spaces or '\t' for a tab).
    """
    indentation_levels = set()
    indent_pattern = re.compile(r'^(\s+)<')

    with open(xml_path, 'r', encoding='utf-8') as file:
        for line in file:
            match = indent_pattern.match(line)
            if match:
                indent = match.group(1)
                indentation_levels.add(indent)

    if not indentation_levels:
        return '    '  # Default to four spaces if no indentation found

    # Convert indentation levels to lengths
    sorted_indents = sorted(indentation_levels, key=lambda x: len(x))

    # Find the smallest non-zero indentation increment
    indent_lengths = sorted([len(indent) for indent in sorted_indents if len(indent) > 0])

    # Calculate differences between consecutive indent lengths
    differences = [
        indent_lengths[i] - indent_lengths[i - 1]
        for i in range(1, len(indent_lengths))
        if indent_lengths[i] - indent_lengths[i - 1] > 0
    ]

    if differences:
        per_level_indent_len = min(differences)
    else:
        # If differences list is empty, assume per-level indent is the smallest indented level
        per_level_indent_len = len(sorted_indents[0])

    # Identify the indent string with length equal to per_level_indent_len
    for indent in sorted_indents:
        if len(indent) == per_level_indent_len:
            per_level_indent = indent
            break
    else:
        # Fallback if no exact match found
        per_level_indent = '    '

    return per_level_indent

def generate_xpath(element, root):
    """
    Generates the XPath for a given element within the XML tree.
    Prefers using '//' with attribute-based identification for nested elements
    to provide more flexibility while ensuring uniqueness.

    Args:
        element (etree.Element): The element for which to generate the XPath.
        root (etree.Element): The root element of the XML tree.

    Returns:
        str: The XPath expression pointing to the element.
    """
    # Attempt to create an absolute XPath
    path = []
    current = element
    while current is not None and current is not root:
        parent = current.getparent()
        if parent is None:
            break  # Reached the root
        siblings = parent.findall(current.tag)

        # Debug: Log current.tag and type
        if not isinstance(current.tag, str):
            logging.error(f"current.tag is not a string: {current.tag} (type: {type(current.tag)})")
            sys.exit(1)

        if len(siblings) == 1:
            path.insert(0, f'/{current.tag}')
        else:
            # Use unique attributes for identification
            unique_attr = None
            for attr in ['id', 'name', 'key', 'ref', 'value']:  # Add attributes as needed
                if attr in current.attrib:
                    unique_attr = attr
                    break
            if unique_attr:
                # Escape quotes in attribute values
                attr_value = current.attrib[unique_attr].replace('"', '&quot;')
                path.insert(0, f'/{current.tag}[@{unique_attr}="{attr_value}"]')
            else:
                # Fallback to positional index
                try:
                    index = siblings.index(current) + 1  # XPath indices are 1-based
                except ValueError:
                    logging.error(f"Element {current.tag} not found among its siblings.")
                    sys.exit(1)
                path.insert(0, f'/{current.tag}[{index}]')
        current = parent
    absolute_xpath = ''.join(path)
    if not absolute_xpath.startswith('/'):
        absolute_xpath = '/' + absolute_xpath

    # Determine the depth of the element
    depth = absolute_xpath.count('/')

    # If more than two levels deep, prefer using '//' with attributes
    if depth > 2:
        # Attempt to generate a '//tag[@attr="value"]' XPath
        for attr in ['id', 'name', 'key', 'ref', 'value']:
            if attr in element.attrib:
                attr_value = element.attrib[attr].replace('"', '&quot;')
                xpath = f'//{element.tag}[@{attr}="{attr_value}"]'
                # Optional: Verify uniqueness
                try:
                    matches = root.xpath(xpath)
                except etree.XPathError as e:
                    logging.error(f"Invalid XPath generated: {xpath} | Error: {e}")
                    continue
                if len(matches) == 1:
                    return xpath
        # If no unique attribute found, fallback to absolute XPath
    return absolute_xpath

def generate_key(element, parent_key, index):
    """
    Generates a unique key for an element based on a unique identifier or position.

    Args:
        element (etree.Element): The XML element.
        parent_key (str): The XPath of the parent element.
        index (int): The position index of the element among its siblings.

    Returns:
        str: A unique key for the element.
    """
    # Prioritize 'id' attribute if available
    unique_id = element.get('id')
    if unique_id:
        return f"{parent_key}/{element.tag}[@id='{unique_id}']"
    else:
        # Fallback to positional index
        return f"{parent_key}/{element.tag}[{index}]"

def compare_elements(original_elem, modified_elem, diff_root, indent_str, parent_key=''):
    """
    Compares two XML elements and records the differences as add, replace, or remove operations.

    Args:
        original_elem (etree.Element): Element from the original XML.
        modified_elem (etree.Element): Element from the modified XML.
        diff_root (etree.Element): Root of the diff XML tree to append operations.
        indent_str (str): The detected per-level indentation string.
        parent_key (str): The XPath of the parent element.
    """
    # Generate unique keys for both elements
    original_key = generate_key(original_elem, parent_key, 1)  # Assuming first occurrence
    modified_key = generate_key(modified_elem, parent_key, 1)

    # Compare tag
    if original_elem.tag != modified_elem.tag:
        # Replace the entire element
        sel = generate_xpath(original_elem, original_elem.getroottree().getroot())
        replace_op = etree.SubElement(diff_root, 'replace', sel=sel)
        # Clone the modified element
        replacement = etree.fromstring(etree.tostring(modified_elem))
        replace_op.append(replacement)
        logging.debug(f"Replaced entire element '{original_elem.tag}' with '{modified_elem.tag}'.")
        return

    # Compare attributes
    original_attrib = original_elem.attrib
    modified_attrib = modified_elem.attrib

    # Attributes to add or replace
    for attr, value in modified_attrib.items():
        if attr not in original_attrib:
            # Attribute added
            sel = f"{generate_xpath(original_elem, original_elem.getroottree().getroot())}/@{attr}"
            add_op = etree.SubElement(diff_root, 'add', sel=sel, pos='after')
            add_op.text = value
            logging.debug(f"Added attribute '{attr}' with value '{value}' to element '{original_elem.tag}'.")
        elif original_attrib[attr] != value:
            # Attribute replaced
            sel = f"{generate_xpath(original_elem, original_elem.getroottree().getroot())}/@{attr}"
            replace_op = etree.SubElement(diff_root, 'replace', sel=sel)
            replace_op.text = value
            logging.debug(f"Replaced attribute '{attr}' value from '{original_attrib[attr]}' to '{value}' in element '{original_elem.tag}'.")

    # Attributes to remove
    for attr in original_attrib:
        if attr not in modified_attrib:
            sel = f"{generate_xpath(original_elem, original_elem.getroottree().getroot())}/@{attr}"
            remove_op = etree.SubElement(diff_root, 'remove', sel=sel)
            logging.debug(f"Removed attribute '{attr}' from element '{original_elem.tag}'.")

    # Compare text
    original_text = original_elem.text.strip() if original_elem.text else ''
    modified_text = modified_elem.text.strip() if modified_elem.text else ''
    if original_text != modified_text:
        sel = generate_xpath(original_elem, original_elem.getroottree().getroot())
        if modified_text:
            # Replace text
            replace_op = etree.SubElement(diff_root, 'replace', sel=sel)
            replace_op.text = modified_text
            logging.debug(f"Replaced text in element '{original_elem.tag}' from '{original_text}' to '{modified_text}'.")
        else:
            # Remove text
            remove_op = etree.SubElement(diff_root, 'remove', sel=f"{sel}/text()")
            logging.debug(f"Removed text from element '{original_elem.tag}'.")

    # Compare children
    original_children = list(original_elem)
    modified_children = list(modified_elem)

    # Build maps with unique keys
    original_map = {}
    for index, child in enumerate(original_children, start=1):
        if not isinstance(child.tag, str):
            logging.error(f"Expected 'child.tag' to be str, but got {type(child.tag)}. Skipping this child.")
            continue  # Skip or handle as needed

        key = generate_key(child, original_key, index)
        original_map[key] = child

    modified_map = {}
    for index, child in enumerate(modified_children, start=1):
        if not isinstance(child.tag, str):
            logging.error(f"Expected 'child.tag' to be str, but got {type(child.tag)}. Skipping this child.")
            continue  # Skip or handle as needed

        key = generate_key(child, original_key, index)
        modified_map[key] = child

    # Detect removed elements
    for key in original_map:
        if key not in modified_map:
            elem = original_map[key]
            sel = generate_xpath(elem, original_elem.getroottree().getroot())
            remove_op = etree.SubElement(diff_root, 'remove', sel=sel)
            logging.debug(f"Marked element '{elem.tag}' for removal.")

    # Detect added elements by comparing unique keys
    for key in modified_map:
        if key not in original_map:
            elem = modified_map[key]
            parent = elem.getparent()

            # Get list of siblings from the parent
            siblings = list(parent)
            idx = siblings.index(elem)  # index of the newly added element among its parent's children

            # Determine position relative to siblings
            if idx > 0:
                # We have a previous sibling
                ref_sibling = siblings[idx - 1]
                sel = generate_xpath(ref_sibling, original_elem.getroottree().getroot())
                pos = 'after'
            else:
                # No previous sibling, try next sibling for "before"
                if len(siblings) > 1:
                    ref_sibling = siblings[idx + 1]
                    sel = generate_xpath(ref_sibling, original_elem.getroottree().getroot())
                    pos = 'before'
                else:
                    # No siblings at all, fallback to parent
                    sel = generate_xpath(parent, original_elem.getroottree().getroot())
                    pos = 'after'

            add_op = etree.SubElement(diff_root, 'add', sel=sel, pos=pos)
            add_op.append(etree.fromstring(etree.tostring(elem)))
            logging.debug(f"Marked '{elem.tag}' for addition {pos} sibling/parent reference.")

    # Recursively compare existing children
    for key in original_map:
        if key in modified_map:
            # Recursive comparison
            compare_elements(original_map[key], modified_map[key], diff_root, indent_str, parent_key=original_key)

def generate_diff(original_tree, modified_tree, indent_str):
    """
    Generates the diff XML operations between original and modified XML trees.

    Args:
        original_tree (etree.ElementTree): Original XML tree.
        modified_tree (etree.ElementTree): Modified XML tree.
        indent_str (str): The detected per-level indentation string.

    Returns:
        etree.Element: Root of the diff XML tree.
    """
    diff_root = etree.Element('diff')

    # Compare the root elements
    compare_elements(original_tree.getroot(), modified_tree.getroot(), diff_root, indent_str)

    return diff_root

def validate_diff_xml(diff_xml_path, xsd_path):
    """
    Validates the generated diff XML against the provided XSD schema.

    Args:
        diff_xml_path (str): Path to the generated diff XML file.
        xsd_path (str): Path to the XSD schema file.
    """
    try:
        with open(xsd_path, 'rb') as f:
            xmlschema_doc = etree.parse(f)
            xmlschema = etree.XMLSchema(xmlschema_doc)
    except Exception as e:
        logging.error(f"Error parsing XSD: {e}")
        return

    try:
        with open(diff_xml_path, 'rb') as f:
            xml_doc = etree.parse(f)
    except Exception as e:
        logging.error(f"Error parsing diff XML: {e}")
        return

    if xmlschema.validate(xml_doc):
        logging.info(f"Validation successful: {diff_xml_path} is valid against {xsd_path}")
    else:
        logging.error(f"Validation failed: {diff_xml_path} is not valid against {xsd_path}")
        for error in xmlschema.error_log:
            logging.error(error.message)
        return

def process_single_file(original_xml_path, modified_xml_path, diff_xml_path, diff_xsd_path):
    """
    Processes a single trio of original, modified, and diff XML files.

    Args:
        original_xml_path (str): Path to the original XML file.
        modified_xml_path (str): Path to the modified XML file.
        diff_xml_path (str): Path for the output diff XML file or directory.
        diff_xsd_path (str): Path to the diff.xsd schema file.
    """
    # Check if original XML file exists
    if not os.path.isfile(original_xml_path):
        logging.error(f"Original XML file does not exist: {original_xml_path}")
        return

    # Check if modified XML file exists
    if not os.path.isfile(modified_xml_path):
        logging.error(f"Modified XML file does not exist: {modified_xml_path}")
        return

    # Check if diff_xml is a directory
    if os.path.isdir(diff_xml_path):
        original_filename = os.path.basename(original_xml_path)
        diff_xml_path = os.path.join(diff_xml_path, original_filename)
        logging.info(f"Diff XML will be saved as: {diff_xml_path}")
    else:
        # Ensure the output directory exists
        diff_xml_dir = os.path.dirname(diff_xml_path)
        if diff_xml_dir and not os.path.exists(diff_xml_dir):
            try:
                os.makedirs(diff_xml_dir)
                logging.info(f"Created output directory: {diff_xml_dir}")
            except Exception as e:
                logging.error(f"Failed to create output directory '{diff_xml_dir}': {e}")
                return

    # Load both XML files
    try:
        original_tree = etree.parse(original_xml_path)
        logging.info(f"Parsed original XML: {original_xml_path}")
    except Exception as e:
        logging.error(f"Error parsing original XML: {e}")
        return

    try:
        modified_tree = etree.parse(modified_xml_path)
        logging.info(f"Parsed modified XML: {modified_xml_path}")
    except Exception as e:
        logging.error(f"Error parsing modified XML: {e}")
        return

    # Detect indentation from original XML
    indent_str = detect_indentation(original_xml_path)
    logging.info(f"Detected indentation: '{repr(indent_str)}'")

    # Generate the diff XML
    diff_tree_root = generate_diff(original_tree, modified_tree, indent_str)

    # Create an ElementTree for diff
    diff_tree = etree.ElementTree(diff_tree_root)

    # Re-indent the entire XML tree for consistent formatting
    if hasattr(etree, 'indent'):
        etree.indent(diff_tree, space=indent_str)
    # Write the diff XML to file
    try:
        diff_tree.write(diff_xml_path, pretty_print=True, xml_declaration=True, encoding='utf-8')
        logging.info(f"Diff XML written to {diff_xml_path}")
    except Exception as e:
        logging.error(f"Error writing diff XML: {e}")
        return

    # Validate the diff XML against diff.xsd if available
    if diff_xsd_path:
        validate_diff_xml(diff_xml_path, diff_xsd_path)
    else:
        logging.info("Skipping validation as diff.xsd was not provided or found.")

def process_directories(original_dir, modified_dir, diff_dir, xsd_path):
    """
    Processes directories by recursively generating diffs for each XML file.

    Args:
        original_dir (str): Path to the original XML directory.
        modified_dir (str): Path to the modified XML directory.
        diff_dir (str): Path for the output diff XML directory.
        xsd_path (str): Path to the diff.xsd schema file.
    """
    for root, _, files in os.walk(original_dir):
        for file in files:
            if file.lower().endswith('.xml'):
                original_file_path = os.path.join(root, file)
                # Determine the relative path
                relative_path = os.path.relpath(original_file_path, original_dir)
                modified_file_path = os.path.join(modified_dir, relative_path)
                diff_file_path = os.path.join(diff_dir, relative_path)

                # Ensure the modified file exists
                if not os.path.isfile(modified_file_path):
                    logging.warning(f"Modified file does not exist: {modified_file_path}. Skipping.")
                    continue

                # Ensure the output directory exists
                diff_file_dir = os.path.dirname(diff_file_path)
                if not os.path.exists(diff_file_dir):
                    try:
                        os.makedirs(diff_file_dir)
                        logging.info(f"Created directory: {diff_file_dir}")
                    except Exception as e:
                        logging.error(f"Failed to create directory '{diff_file_dir}': {e}")
                        continue

                # Process the single file trio
                process_single_file(original_file_path, modified_file_path, diff_file_path, xsd_path)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    original_xml_path, modified_xml_path, diff_xml_path, diff_xsd_path = parse_arguments()

    # Determine the path to diff.xsd
    if diff_xsd_path:
        if not os.path.isfile(diff_xsd_path):
            logging.error(f"diff.xsd file does not exist: {diff_xsd_path}")
            sys.exit(1)
        else:
            logging.info(f"Using provided diff.xsd path: {diff_xsd_path}")
    else:
        # Look for 'diff.xsd' in the same directory as the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_xsd_path = os.path.join(script_dir, 'diff.xsd')
        if os.path.isfile(default_xsd_path):
            diff_xsd_path = default_xsd_path
            logging.info(f"Using default diff.xsd path: {diff_xsd_path}")
        else:
            logging.error("diff.xsd not provided and not found in the script's directory.")
            sys.exit(1)

    # Determine if input paths are files or directories
    original_is_dir = os.path.isdir(original_xml_path)
    modified_is_dir = os.path.isdir(modified_xml_path)
    diff_is_dir = os.path.isdir(diff_xml_path)

    if original_is_dir and modified_is_dir and diff_is_dir:
        logging.info("Processing directories recursively.")
        process_directories(original_xml_path, modified_xml_path, diff_xml_path, diff_xsd_path)
    elif not original_is_dir and not modified_is_dir:
        logging.info("Processing single trio of files.")
        process_single_file(original_xml_path, modified_xml_path, diff_xml_path, diff_xsd_path)
    else:
        logging.error("Mismatch in input paths. Original and modified paths should be directories or both should be files.")
        sys.exit(1)

if __name__ == "__main__":
    main()