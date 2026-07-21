from iaglobal.agents.coder_agent import CodeArtifact
from iaglobal.graphs.artifact import Artifact, SolutionArtifact


class TestCodeArtifactFromRaw:
    """CodeArtifact.from_raw() é o contrato de entrada do pipeline — todo shape
    que pode sair de um nó (None, str, dict, objeto com .code) deve ser
    normalizado sem stringificar estruturas arbitrárias."""

    def test_none_returns_empty(self):
        a = CodeArtifact.from_raw(None)
        assert a.code == ""
        assert a.files == {}

    def test_str_returns_code(self):
        a = CodeArtifact.from_raw("print(1)")
        assert a.code == "print(1)"
        assert a.files == {}

    def test_dict_with_code_key(self):
        a = CodeArtifact.from_raw(
            {"code": "x = 1", "files": {"a.py": "y=2"}, "score": 0.9}
        )
        assert a.code == "x = 1"
        assert a.files == {"a.py": "y=2"}
        assert a.score == 0.9

    def test_dict_with_output_string(self):
        a = CodeArtifact.from_raw({"output": "print(2)"})
        assert a.code == "print(2)"
        assert a.files == {}

    def test_dict_with_output_dict_with_code(self):
        a = CodeArtifact.from_raw({"output": {"code": "nested"}})
        assert a.code == "nested"
        assert a.files == {}

    def test_dict_with_output_dict_without_code(self):
        a = CodeArtifact.from_raw({"output": {"score": 0.8}})
        assert a.code == ""
        assert a.files == {}

    def test_dict_with_files_but_no_code(self):
        a = CodeArtifact.from_raw({"files": {"b.py": "z=3"}})
        assert a.code == ""
        assert a.files == {}

    def test_files_only_never_promotes_first_file_to_code(self):
        a = CodeArtifact.from_raw({"files": {"main.py": "print('hello')"}})
        assert a.code == ""

    def test_dict_with_neither_code_output_files(self):
        a = CodeArtifact.from_raw({"response": "ok", "score": 0.8})
        assert a.code == ""

    def test_arbitrary_dict_never_strified(self):
        raw = {"response": "ok", "score": 0.8}
        a = CodeArtifact.from_raw(raw)
        assert a.code != str(raw)
        assert a.code == ""
        assert a.files == {}

    def test_solution_artifact_has_code_attr(self):
        sa = SolutionArtifact(code="sol", files={"s.py": "print(1)"}, score=0.95)
        a = CodeArtifact.from_raw(sa)
        assert a.code == "sol"
        assert a.files == {"s.py": "print(1)"}
        assert a.score == 0.95

    def test_artifact_has_no_code_attr_returns_empty(self):
        art = Artifact(content="some content", type="code")
        a = CodeArtifact.from_raw(art)
        assert a.code == ""
        assert a.files == {}

    def test_code_artifact_passthrough(self):
        original = CodeArtifact(code="x=1", files={"f.py": "y=2"}, score=0.5)
        a = CodeArtifact.from_raw(original)
        assert a is original

    def test_raw_code_none_returns_empty(self):
        a = CodeArtifact.from_raw({"code": None})
        assert a.code == ""

    def test_raw_code_empty_str_returns_empty(self):
        a = CodeArtifact.from_raw({"code": ""})
        assert a.code == ""

    def test_dict_output_none_returns_empty(self):
        a = CodeArtifact.from_raw({"output": None})
        assert a.code == ""

    def test_object_with_code_empty_returns_empty(self):
        class R:
            code = ""
            files = {}

        a = CodeArtifact.from_raw(R())
        assert a.code == ""
