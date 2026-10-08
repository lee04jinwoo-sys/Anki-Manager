import unittest
import requests

BASE_URL = "http://127.0.0.1:8001"

class TestAnkiManagerSystem(unittest.TestCase):

    def test_01_static_web_ui(self):
        """프론트엔드 HTML, CSS, JS 무결성 검증"""
        r_home = requests.get(f"{BASE_URL}/")
        self.assertEqual(r_home.status_code, 200)
        self.assertIn("source-grid", r_home.text)
        self.assertIn("source-card-btn", r_home.text)
        self.assertIn("progress-area", r_home.text)
        self.assertIn("close-logs-btn", r_home.text)

        r_css = requests.get(f"{BASE_URL}/css/styles.css")
        self.assertEqual(r_css.status_code, 200)
        self.assertIn(".source-card-btn", r_css.text)

        r_js = requests.get(f"{BASE_URL}/js/app.js")
        self.assertEqual(r_js.status_code, 200)
        self.assertIn("startGlobalLogPolling", r_js.text)
        self.assertIn("closeLogsBtn", r_js.text)

    def test_02_anki_status_api(self):
        """AnkiConnect 상태 API 검증"""
        r = requests.get(f"{BASE_URL}/api/status/anki")
        self.assertEqual(r.status_code, 200)
        self.assertIn("connected", r.json())

    def test_03_stats_api(self):
        """덱별 통계 현황 API 검증"""
        r = requests.get(f"{BASE_URL}/api/stats/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("status", data)

    def test_04_leech_candidates(self):
        """Leech 카드 후보 진단 API 검증"""
        r = requests.get(f"{BASE_URL}/api/leech/candidates?mode=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("candidates", r.json())

    def test_05_workflow_state_engine(self):
        """로그 초기화 및 워크플로우 상태 엔진 검증"""
        r_clear = requests.post(f"{BASE_URL}/api/workflow/clear-logs")
        self.assertEqual(r_clear.status_code, 200)

        r_status = requests.get(f"{BASE_URL}/api/workflow/status")
        self.assertEqual(r_status.status_code, 200)
        state = r_status.json()
        self.assertFalse(state.get("is_running", True))
        self.assertEqual(state.get("progress", 0), 0)
        self.assertEqual(len(state.get("logs", [])), 0)

    def test_06_leech_batch_actions(self):
        """Leech 일괄 조치(태그, 일시정지, 리셋) 엔드포인트 검증"""
        for action in ["tag", "suspend", "reset"]:
            r = requests.post(f"{BASE_URL}/api/leech/{action}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("status", r.json())

    def test_07_organize_and_design_routes(self):
        """중복 정리 및 디자인 엔드포인트 검증"""
        r_dup = requests.post(f"{BASE_URL}/api/organize/duplicates")
        self.assertEqual(r_dup.status_code, 200)

        r_sync_design = requests.post(f"{BASE_URL}/api/design/sync")
        self.assertEqual(r_sync_design.status_code, 200)

        # Cleanup logs
        requests.post(f"{BASE_URL}/api/workflow/clear-logs")

if __name__ == "__main__":
    unittest.main()
