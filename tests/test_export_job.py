"""An export left "running" by a process that died (app closed mid-export) must not block the Publicar button forever."""
import datetime, os, subprocess, sys
from tests.base import ProjectCase, P


class ExportJobTest(ProjectCase):
    def test_dead_pid_is_marked_interrupted(self):
        self.make_project()
        p = subprocess.Popen([sys.executable, "-c", "pass"]); p.wait()           # a pid that has finished
        P.job("t1", "export", step="Cortando", pct=3, done=False, pid=p.pid)
        self.assertFalse(P.export_running("t1"))
        j = P.read_job("t1", "export")
        self.assertTrue(j["done"]); self.assertEqual(j["step"], "Interrompida"); self.assertIn("fechado", j["error"])

    def test_live_pid_keeps_running(self):
        self.make_project()
        P.job("t1", "export", step="Renderizando", pct=50, done=False, pid=os.getpid())
        self.assertTrue(P.export_running("t1"))
        self.assertFalse(P.read_job("t1", "export")["done"])

    def test_old_job_without_pid_expires(self):
        self.make_project()
        P.job("t1", "export", step="Cortando", pct=3, done=False)
        j = P.read_job("t1", "export"); j["t"] = (datetime.datetime.now() - datetime.timedelta(hours=5)).isoformat(timespec="seconds")
        P._write_json(P.folder("t1") / "export.json", j)
        self.assertFalse(P.export_running("t1"))

    def test_fresh_job_without_pid_is_running(self):             # the server writes "Começando" before the process sets its pid
        self.make_project()
        P.job("t1", "export", step="Começando", pct=1, done=False)
        self.assertTrue(P.export_running("t1"))

    def test_no_job_and_done_job(self):
        self.make_project()
        self.assertFalse(P.export_running("t1"))
        P.job("t1", "export", step="Pronto", done=True)
        self.assertFalse(P.export_running("t1"))
