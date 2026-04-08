"""Unit tests for executor/ship.py — code parser, object store writer, git committer."""

import pytest

pytestmark = pytest.mark.asyncio


def test_parse_fenced_blocks():
    from executor.ship import parse_generated_code

    text = '''Here is the blog app:

```python
# app.py
from flask import Flask
app = Flask(__name__)

@app.route("/")
def index():
    return "<h1>My Blog</h1>"
```

```html
<!-- index.html -->
<html><body><h1>Blog</h1></body></html>
```

```css
/* style.css */
body { font-family: sans-serif; }
```
'''
    files = parse_generated_code(text)
    assert len(files) == 3
    names = [f for f, _ in files]
    assert "app.py" in names
    assert "index.html" in names
    assert "style.css" in names

    # Check filename comment was stripped from content
    app_content = next(c for f, c in files if f == "app.py")
    assert "# app.py" not in app_content
    assert "Flask" in app_content


def test_parse_filename_comment_variations():
    from executor.ship import parse_generated_code

    text = '''```python
# filename: main.py
import flask
```

```javascript
// filename: server.js
console.log("hi")
```

```html
<!-- filename: page.html -->
<h1>Hello</h1>
```
'''
    files = parse_generated_code(text)
    assert len(files) == 3
    names = [f for f, _ in files]
    assert "main.py" in names
    assert "server.js" in names
    assert "page.html" in names


def test_parse_no_fenced_blocks_fallback():
    from executor.ship import parse_generated_code

    text = "print('hello world')\nprint('goodbye')"
    files = parse_generated_code(text)
    assert len(files) == 1
    assert files[0][0] == "main.py"
    assert "hello world" in files[0][1]


def test_parse_no_language_tag():
    from executor.ship import parse_generated_code

    text = "```\nsome content here\n```"
    files = parse_generated_code(text)
    assert len(files) == 1
    assert files[0][1] == "some content here"


def test_parse_deduplicates_filenames():
    from executor.ship import parse_generated_code

    text = '''```python
# app.py
print("first")
```

```python
# app.py
print("second")
```
'''
    files = parse_generated_code(text)
    assert len(files) == 2
    names = [f for f, _ in files]
    assert len(set(names)) == 2  # No duplicates


def test_parse_language_fallback_filenames():
    from executor.ship import parse_generated_code

    text = '''```python
x = 1
```

```html
<div>hi</div>
```

```dockerfile
FROM python:3.12
```
'''
    files = parse_generated_code(text)
    assert len(files) == 3
    names = [f for f, _ in files]
    assert "main.py" in names
    assert "index.html" in names
    assert "Dockerfile" in names


def test_detect_app_port_from_expose(tmp_path):
    from executor.ship import _detect_app_port

    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.12\nEXPOSE 3000\nCMD ['python', 'app.py']")
    port = _detect_app_port(str(tmp_path), [("app.py", "print(1)")])
    assert port == 3000


def test_detect_app_port_flask_default(tmp_path):
    from executor.ship import _detect_app_port

    port = _detect_app_port(str(tmp_path), [("app.py", "from flask import Flask")])
    assert port == 5000


def test_detect_app_port_generic_default(tmp_path):
    from executor.ship import _detect_app_port

    port = _detect_app_port(str(tmp_path), [("app.py", "print('hello')")])
    assert port == 8080


def test_find_free_port():
    from executor.ship import _find_free_port

    port = _find_free_port(start=19000)
    assert 19000 <= port < 19100
