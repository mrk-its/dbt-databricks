import pytest
from dbt.tests import util
from tests.functional.adapter.warehouse_per_model import fixtures


class BaseWarehousePerModel:
    args_formatter = ""

    @pytest.fixture(scope="class")
    def seeds(self):
        return {
            "source.csv": fixtures.source,
        }

    @pytest.fixture(scope="class")
    def models(self):
        d = dict()
        d["target4.sql"] = fixtures.target3
        return {
            "target.sql": fixtures.target,
            "target2.sql": fixtures.target2,
            "target3.sql": fixtures.target3,
            "schema.yml": fixtures.model_schema,
            "special": d,
        }


class BaseSpecifyingCompute(BaseWarehousePerModel):
    """Base class for testing various ways to specify a warehouse."""

    def test_wpm(self, project):
        util.run_dbt(["seed"])
        models = project.test_config.get("model_names")
        for model_name in models:
            # Since the profile doesn't define a compute resource named 'alternate_warehouse'
            # we should fail with an error if the warehouse specified for the model is
            # correctly handled.
            res = util.run_dbt(["run", "--select", model_name], expect_pass=False)
            msg = res.results[0].message
            assert "Compute resource alternate_warehouse does not exist" in msg
            assert model_name in msg


class TestSpecifyingInConfigBlock(BaseSpecifyingCompute):
    @pytest.fixture(scope="class")
    def test_config(self):
        return {"model_names": ["target"]}


class TestSpecifyingInSchemaYml(BaseSpecifyingCompute):
    @pytest.fixture(scope="class")
    def test_config(self):
        return {"model_names": ["target2"]}


class TestSpecifyingForProjectModels(BaseSpecifyingCompute):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "models": {
                "+databricks_compute": "alternate_warehouse",
            }
        }

    @pytest.fixture(scope="class")
    def test_config(self):
        return {"model_names": ["target3"]}


class TestSpecifyingForProjectModelsInFolder(BaseSpecifyingCompute):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "models": {
                "test": {
                    "special": {
                        "+databricks_compute": "alternate_warehouse",
                    },
                },
            }
        }

    @pytest.fixture(scope="class")
    def test_config(self):
        return {"model_names": ["target4"]}


class TestWarehousePerModel(BaseWarehousePerModel):
    @pytest.fixture(scope="class")
    def profiles_config_update(self, dbt_profile_target):
        outputs = {"default": dbt_profile_target}
        outputs["default"]["compute"] = {
            "alternate_warehouse": {"http_path": dbt_profile_target["http_path"]},
            "alternate_warehouse2": {"http_path": dbt_profile_target["http_path"]},
            "alternate_warehouse3": {"http_path": dbt_profile_target["http_path"]},
        }
        return {"test": {"outputs": outputs, "target": "default"}}

    @pytest.fixture(scope="class")
    def seeds(self):
        return {
            "source.csv": fixtures.source,
            "properties.yml": fixtures.seed_properties,
        }

    @pytest.fixture(scope="class")
    def snapshots(self):
        return {
            "target_snap.sql": fixtures.target_snap,
        }

    def test_wpm(self, project):
        _, log = util.run_dbt_and_capture(["--debug", "seed"])
        assert "`source` using compute resource 'alternate_warehouse2'" in log

        _, log = util.run_dbt_and_capture(["--debug", "run", "--select", "target", "target3"])
        assert "`target` using compute resource 'alternate_warehouse'" in log
        assert "`target3` using default compute resource" in log

        _, log = util.run_dbt_and_capture(["--debug", "snapshot"])
        assert "`target_snap` using compute resource 'alternate_warehouse3'" in log

        util.check_relations_equal(project.adapter, ["target", "source"])
