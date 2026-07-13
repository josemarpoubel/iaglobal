# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for LocalSummarizer — compressão multi-linguagem."""

from iaglobal.search.local_summarizer import LocalSummarizer


class TestLocalSummarizer:
    """Valida extração de assinaturas, compressão e remoção de ruído."""

    def test_compress_empty_output(self):
        t, o = LocalSummarizer.compress("", "")
        assert o == ""

    def test_compress_preserves_python_code(self):
        output = "```python\ndef hello(name):\n    return f'Hello {name}'\n```"
        t, o = LocalSummarizer.compress("test", output)
        assert "hello" in o
        assert "def hello" in o

    def test_compress_preserves_javascript(self):
        output = "```javascript\nfunction sum(a, b) {\n  return a + b;\n}\n```"
        _, o = LocalSummarizer.compress("", output)
        assert "function sum" in o

    def test_compress_preserves_typescript_interface(self):
        output = "```typescript\ninterface User {\n  id: number;\n}\n```"
        _, o = LocalSummarizer.compress("", output)
        assert "interface User" in o

    def test_compress_preserves_go(self):
        output = '```go\nfunc main() {\n  fmt.Println("ok")\n}\n```'
        _, o = LocalSummarizer.compress("", output)
        assert "func main" in o

    def test_compress_preserves_rust(self):
        output = "```rust\nfn fibonacci(n: u32) -> u32 {\n  0\n}\n```"
        _, o = LocalSummarizer.compress("", output)
        assert "fn fibonacci" in o

    def test_compress_preserves_sql_ddl(self):
        output = "```sql\nCREATE TABLE users (\n  id INT PRIMARY KEY\n);\n```"
        _, o = LocalSummarizer.compress("", output)
        assert "CREATE TABLE" in o

    def test_compress_tolerant_to_weird_indentation(self):
        output = "```python\n  def  my_function(x,  y):\n     return x+y\n```"
        _, o = LocalSummarizer.compress("", output)
        assert "my_function" in o

    def test_remove_boilerplate_portuguese(self):
        output = "Você é um especialista em Python.\nRetorne APENAS o código.\ndef fn(): pass"
        _, o = LocalSummarizer.compress("", output)
        assert "def fn()" in o
        assert "Você é" not in o
        assert "Retorne APENAS" not in o

    def test_remove_boilerplate_english(self):
        output = "You are a Python expert.\nReturn ONLY the code.\ndef fn(): pass"
        _, o = LocalSummarizer.compress("", output)
        assert "def fn()" in o
        assert "You are" not in o
        assert "Return ONLY" not in o

    def test_remove_prompt_noise_prefixes(self):
        output = "Seu papel é avaliar código.\ndef fn(): pass\nFormato de saída: JSON."
        cleaned = LocalSummarizer._remove_prompt_noise(output)
        assert "def fn()" in cleaned
        assert "Seu papel" not in cleaned
        assert "Formato de saída" not in cleaned

    def test_dedup_lines_removes_consecutive_duplicates(self):
        text = "linha1\nlinha1\nlinha2"
        result = LocalSummarizer._dedup_lines(text)
        assert result == "linha1\nlinha2"

    def test_dedup_lines_keeps_non_consecutive_duplicates(self):
        text = "linha1\nlinha2\nlinha1"
        result = LocalSummarizer._dedup_lines(text)
        assert result == text

    def test_detect_language_python(self):
        assert LocalSummarizer._detect_language("def foo(): pass") == "python"
        assert LocalSummarizer._detect_language("import os") == "python"

    def test_detect_language_javascript(self):
        assert LocalSummarizer._detect_language("function foo() {}") == "javascript"
        assert LocalSummarizer._detect_language("const x = () => {") == "javascript"

    def test_detect_language_go(self):
        assert LocalSummarizer._detect_language("func main() {") == "go"

    def test_detect_language_sql(self):
        assert LocalSummarizer._detect_language("SELECT * FROM users") == "sql"

    def test_detect_language_unknown(self):
        assert LocalSummarizer._detect_language("whatever") == ""

    def test_compress_task_to_max_chars(self):
        task = "x" * 1000
        t, _ = LocalSummarizer.compress(task, "")
        assert len(t) <= 600

    def test_compress_output_to_max_chars(self):
        output = "```python\n" + ("x" * 5000) + "\n```"
        _, o = LocalSummarizer.compress("", output)
        assert len(o) <= 3000

    def test_extract_code_blocks_fenced(self):
        text = "text\n```python\ncode here\n```\nmore"
        blocks = LocalSummarizer._extract_code_blocks(text)
        assert len(blocks) == 1
        assert "code here" in blocks[0]

    def test_extract_code_blocks_multiple(self):
        text = "```py\na\n```\n...\n```js\nb\n```"
        blocks = LocalSummarizer._extract_code_blocks(text)
        assert len(blocks) >= 2

    def test_compress_mixed_output_has_sections(self):
        output = "```python\ndef fn(): pass\n```\nalgum texto residual"
        _, o = LocalSummarizer.compress("", output)
        assert "[Assinaturas]" in o or "[Codigo/python]" in o or "[Resumo]" in o

    def test_extract_signatures_python(self):
        text = "def hello(name): pass\nclass MyClass:\n    pass\n@decorator\ndef wrapped(): pass"
        sigs = LocalSummarizer._extract_signatures(text)
        assert "hello" in sigs
        assert "class MyClass" in sigs or "MyClass" in sigs
        assert len(sigs.split("\n")) <= 20

    def test_extract_signatures_javascript(self):
        text = "function sum(a, b) {\n  return a + b;\n}\nclass Service {\n}"
        sigs = LocalSummarizer._extract_signatures(text)
        assert "function sum" in sigs or "sum" in sigs
