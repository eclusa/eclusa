'use strict';

/**
 * Minimal YAML parser for eclusa project files and vestibular.
 * Handles the subset of YAML used by project.eclusa and ~/.vestibular:
 *   - String, number, boolean scalars
 *   - Nested objects (indentation-based)
 *   - Block sequences (- item)
 *   - Flow sequences [a, b, c]
 *   - Flow mappings { key: value }
 *   - Quoted strings (single and double)
 *   - Comments (#)
 *   - Multi-line strings (literal | and folded >)
 *
 * NOT supported: anchors, aliases, tags, complex keys, merge keys.
 * This is intentional — project.eclusa uses a well-defined subset.
 */

function parseYaml(text) {
  const lines = text.split('\n');
  let i = 0;

  function currentLine() { return i < lines.length ? lines[i] : null; }
  function advance() { i++; }

  function indentOf(line) {
    const m = line.match(/^(\s*)/);
    return m ? m[1].length : 0;
  }

  function stripComment(line) {
    // Don't strip # inside quoted strings
    let inSingle = false, inDouble = false;
    for (let j = 0; j < line.length; j++) {
      const c = line[j];
      if (c === "'" && !inDouble) inSingle = !inSingle;
      else if (c === '"' && !inSingle) inDouble = !inDouble;
      else if (c === '#' && !inSingle && !inDouble) {
        return line.slice(0, j).trimEnd();
      }
    }
    return line;
  }

  function parseScalar(raw) {
    const s = raw.trim();
    if (s === '' || s === '~' || s === 'null') return null;
    if (s === 'true') return true;
    if (s === 'false') return false;
    if (/^-?\d+$/.test(s)) return parseInt(s, 10);
    if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s);
    // Quoted string
    if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
      return s.slice(1, -1).replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\'/g, "'");
    }
    return s;
  }

  function parseFlowSequence(s) {
    // [a, b, c] or [{...}, ...]
    const inner = s.slice(1, -1).trim();
    if (inner === '') return [];
    const items = [];
    let depth = 0, start = 0, inQ = false, qChar = '';
    for (let j = 0; j <= inner.length; j++) {
      const c = inner[j];
      if (inQ) {
        if (c === qChar) inQ = false;
        continue;
      }
      if (c === '"' || c === "'") { inQ = true; qChar = c; continue; }
      if (c === '[' || c === '{') depth++;
      else if (c === ']' || c === '}') depth--;
      else if ((c === ',' || j === inner.length) && depth === 0) {
        const item = inner.slice(start, j).trim();
        if (item.startsWith('{')) items.push(parseFlowMapping(item));
        else if (item.startsWith('[')) items.push(parseFlowSequence(item));
        else items.push(parseScalar(item));
        start = j + 1;
      }
    }
    return items;
  }

  function parseFlowMapping(s) {
    const inner = s.slice(1, -1).trim();
    if (inner === '') return {};
    const obj = {};
    let depth = 0, start = 0, inQ = false, qChar = '';
    for (let j = 0; j <= inner.length; j++) {
      const c = inner[j];
      if (inQ) {
        if (c === qChar) inQ = false;
        continue;
      }
      if (c === '"' || c === "'") { inQ = true; qChar = c; continue; }
      if (c === '[' || c === '{') depth++;
      else if (c === ']' || c === '}') depth--;
      else if ((c === ',' || j === inner.length) && depth === 0) {
        const pair = inner.slice(start, j).trim();
        const colonIdx = pair.indexOf(':');
        if (colonIdx > 0) {
          const key = pair.slice(0, colonIdx).trim();
          const val = pair.slice(colonIdx + 1).trim();
          if (val.startsWith('{')) obj[key] = parseFlowMapping(val);
          else if (val.startsWith('[')) obj[key] = parseFlowSequence(val);
          else obj[key] = parseScalar(val);
        }
        start = j + 1;
      }
    }
    return obj;
  }

  function parseBlockScalar(indent, marker) {
    // Literal (|) or folded (>)
    const lines_collected = [];
    while (i < lines.length) {
      const line = currentLine();
      if (line.trim() === '' || indentOf(line) > indent) {
        lines_collected.push(line.slice(Math.min(indent + 2, line.length)));
        advance();
      } else {
        break;
      }
    }
    // Remove trailing empty lines
    while (lines_collected.length && lines_collected[lines_collected.length - 1].trim() === '') {
      lines_collected.pop();
    }
    if (marker === '|') return lines_collected.join('\n');
    // Folded: join lines with spaces, preserve double newlines
    return lines_collected.join('\n').replace(/([^\n])\n([^\n])/g, '$1 $2');
  }

  function parseValue(raw, indent) {
    const trimmed = raw.trim();
    if (trimmed === '' || trimmed === '~') return null;
    if (trimmed.startsWith('[')) return parseFlowSequence(trimmed);
    if (trimmed.startsWith('{')) return parseFlowMapping(trimmed);
    if (trimmed === '|' || trimmed === '|+' || trimmed === '|-') return parseBlockScalar(indent, '|');
    if (trimmed === '>' || trimmed === '>+' || trimmed === '>-') return parseBlockScalar(indent, '>');
    return parseScalar(trimmed);
  }

  function parseBlock(minIndent) {
    const result = {};
    let isList = false;

    // Peek ahead to determine if this is a list or map
    while (i < lines.length) {
      const line = currentLine();
      if (line === null) break;
      const stripped = stripComment(line);
      if (stripped.trim() === '') { advance(); continue; }
      const ind = indentOf(stripped);
      if (ind < minIndent) break;
      if (stripped.trim().startsWith('- ') || stripped.trim() === '-') { isList = true; }
      break;
    }

    if (isList) return parseSequenceBlock(minIndent);
    return parseMappingBlock(minIndent);
  }

  function parseSequenceBlock(minIndent) {
    const items = [];
    while (i < lines.length) {
      const line = currentLine();
      if (line === null) break;
      const stripped = stripComment(line);
      if (stripped.trim() === '') { advance(); continue; }
      const ind = indentOf(stripped);
      if (ind < minIndent) break;
      const content = stripped.trim();
      if (!content.startsWith('-')) break;
      advance();

      const afterDash = content.slice(1).trim();
      if (afterDash === '') {
        // Block item with nested content
        items.push(parseBlock(ind + 2));
      } else if (afterDash.includes(':') && !afterDash.startsWith('"') && !afterDash.startsWith("'") && !afterDash.startsWith('[') && !afterDash.startsWith('{')) {
        // Inline mapping: - key: value
        const colonIdx = afterDash.indexOf(':');
        const key = afterDash.slice(0, colonIdx).trim();
        const valRaw = afterDash.slice(colonIdx + 1).trim();
        const obj = {};
        if (valRaw === '' || valRaw === '~') {
          obj[key] = null;
        } else if (valRaw.startsWith('[')) {
          obj[key] = parseFlowSequence(valRaw);
        } else if (valRaw.startsWith('{')) {
          obj[key] = parseFlowMapping(valRaw);
        } else {
          obj[key] = parseScalar(valRaw);
        }
        // Check for continuation keys at deeper indent
        while (i < lines.length) {
          const nextLine = currentLine();
          if (!nextLine || nextLine.trim() === '') { if (nextLine !== null) advance(); continue; }
          const nextInd = indentOf(stripComment(nextLine));
          if (nextInd <= ind) break;
          const nextContent = stripComment(nextLine).trim();
          const nextColonIdx = nextContent.indexOf(':');
          if (nextColonIdx > 0) {
            const nk = nextContent.slice(0, nextColonIdx).trim();
            const nv = nextContent.slice(nextColonIdx + 1).trim();
            advance();
            if (nv === '' && i < lines.length && indentOf(lines[i] || '') > nextInd) {
              obj[nk] = parseBlock(nextInd + 2);
            } else {
              obj[nk] = parseValue(nv, nextInd);
            }
          } else {
            break;
          }
        }
        items.push(obj);
      } else if (afterDash.startsWith('[')) {
        items.push(parseFlowSequence(afterDash));
      } else if (afterDash.startsWith('{')) {
        items.push(parseFlowMapping(afterDash));
      } else {
        items.push(parseScalar(afterDash));
      }
    }
    return items;
  }

  function parseMappingBlock(minIndent) {
    const result = {};
    while (i < lines.length) {
      const line = currentLine();
      if (line === null) break;
      const stripped = stripComment(line);
      if (stripped.trim() === '') { advance(); continue; }
      const ind = indentOf(stripped);
      if (ind < minIndent) break;
      if (ind > minIndent && Object.keys(result).length === 0) {
        // Re-adjust minIndent to actual
        return parseMappingBlock(ind);
      }
      if (ind !== minIndent) break;

      const content = stripped.trim();
      const colonIdx = content.indexOf(':');
      if (colonIdx <= 0) { advance(); continue; }

      const key = content.slice(0, colonIdx).trim();
      const valRaw = content.slice(colonIdx + 1);
      advance();

      if (valRaw.trim() === '' || valRaw.trim() === '~') {
        // Check if next lines are indented (nested block)
        if (i < lines.length) {
          const nextLine = currentLine();
          if (nextLine && nextLine.trim() !== '' && indentOf(nextLine) > ind) {
            result[key] = parseBlock(ind + 1);
          } else {
            result[key] = valRaw.trim() === '~' ? null : null;
          }
        } else {
          result[key] = null;
        }
      } else {
        result[key] = parseValue(valRaw, ind);
      }
    }
    return result;
  }

  // Skip leading blank lines and document markers
  while (i < lines.length) {
    const line = currentLine();
    if (line === null) break;
    if (line.trim() === '' || line.trim() === '---') { advance(); continue; }
    break;
  }

  return parseBlock(0);
}

function dumpYaml(obj, indent = 0) {
  const pad = '  '.repeat(indent);
  const lines = [];

  if (Array.isArray(obj)) {
    for (const item of obj) {
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        const entries = Object.entries(item);
        if (entries.length > 0) {
          const [firstKey, firstVal] = entries[0];
          if (isSimple(firstVal)) {
            lines.push(`${pad}- ${firstKey}: ${dumpScalar(firstVal)}`);
          } else {
            lines.push(`${pad}- ${firstKey}:`);
            lines.push(dumpYaml(firstVal, indent + 2));
          }
          for (let j = 1; j < entries.length; j++) {
            const [k, v] = entries[j];
            if (isSimple(v)) {
              lines.push(`${pad}  ${k}: ${dumpScalar(v)}`);
            } else {
              lines.push(`${pad}  ${k}:`);
              lines.push(dumpYaml(v, indent + 2));
            }
          }
        } else {
          lines.push(`${pad}- {}`);
        }
      } else if (isSimple(item)) {
        lines.push(`${pad}- ${dumpScalar(item)}`);
      } else {
        lines.push(`${pad}-`);
        lines.push(dumpYaml(item, indent + 1));
      }
    }
  } else if (obj && typeof obj === 'object') {
    for (const [key, val] of Object.entries(obj)) {
      if (val === undefined) continue;
      if (isSimple(val)) {
        lines.push(`${pad}${key}: ${dumpScalar(val)}`);
      } else if (Array.isArray(val) && val.length > 0 && val.every(isSimple)) {
        lines.push(`${pad}${key}: [${val.map(dumpScalar).join(', ')}]`);
      } else {
        lines.push(`${pad}${key}:`);
        lines.push(dumpYaml(val, indent + 1));
      }
    }
  }

  return lines.join('\n');
}

function isSimple(v) {
  return v === null || typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean';
}

function dumpScalar(v) {
  if (v === null) return 'null';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return String(v);
  if (typeof v === 'string') {
    if (v === '' || /[:{}\[\],&*#?|>!%@`]/.test(v) || v.includes('\n') || /^\s|\s$/.test(v)) {
      return `"${v.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`;
    }
    return v;
  }
  return String(v);
}

module.exports = { parseYaml, dumpYaml };
