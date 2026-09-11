from pathlib import Path

import config


def test_runtime_paths_are_centralized():
    assert config.IMPORT_DATA_DIR == Path(config.IMPORT_DATA_DIR)
    assert config.EXECUTION_RESULT_DB_PATH == Path(config.EXECUTION_RESULT_DB_PATH)
    assert config.EXECUTION_JOB_DB_PATH == Path(config.EXECUTION_JOB_DB_PATH)
    assert config.LOG_DIR == Path(config.LOG_DIR)
    assert config.BACKUP_DIR == Path(config.BACKUP_DIR)


def test_configuration_summary_exposes_safe_non_secret_runtime_settings():
    summary = config.configuration_summary()
    assert summary["execution_result_db_path"] == str(config.EXECUTION_RESULT_DB_PATH)
    assert summary["execution_job_db_path"] == str(config.EXECUTION_JOB_DB_PATH)
    assert summary["log_dir"] == str(config.LOG_DIR)
    assert summary["secret_key_configured"] in {True, False}
    assert summary["encryption_key_configured"] in {True, False}
