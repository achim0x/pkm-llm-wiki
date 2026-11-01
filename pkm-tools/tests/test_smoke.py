import pkm


def test_version():
    assert pkm.__version__


def test_isolated_env(isolated_env):
    assert isolated_env["root"].is_dir()
    assert not (isolated_env["root"] / ".git").exists()
