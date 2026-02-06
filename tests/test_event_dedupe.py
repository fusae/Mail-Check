import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class _FakeDB:
    def __init__(self):
        self._next_id = 1
        self.event_groups = []  # list[dict]

    def execute(self, project_root, sql, params=None, fetchone=False, fetchall=False):
        sql_u = " ".join((sql or "").split()).upper()
        params = params or ()

        # SELECT ... FROM event_groups WHERE hospital_name = ? AND (event_url = ? OR event_url = ?)
        if "FROM EVENT_GROUPS" in sql_u and "SELECT" in sql_u and "EVENT_URL" in sql_u and "LIMIT 1" in sql_u:
            hospital = params[0]
            # params = (hospital, key1) or (hospital, key1, key2)
            keys = set([p for p in params[1:] if isinstance(p, str)])
            rows = [r for r in self.event_groups if r["hospital_name"] == hospital and (r.get("event_url") in keys)]
            rows.sort(key=lambda r: r.get("last_seen_at") or "", reverse=True)
            row = rows[0] if rows else None
            return row if fetchone else ([row] if row else [])

        # SELECT id, fingerprint, total_count, event_url FROM event_groups WHERE hospital_name = ? AND last_seen_at >= ?
        if "FROM EVENT_GROUPS" in sql_u and "FINGERPRINT" in sql_u and "LAST_SEEN_AT" in sql_u and "FETCHALL" not in sql_u:
            hospital = params[0]
            rows = [r for r in self.event_groups if r["hospital_name"] == hospital]
            return rows if fetchall else (rows[0] if (fetchone and rows) else None)

        # UPDATE event_groups ... WHERE id = ?
        if sql_u.startswith("UPDATE EVENT_GROUPS"):
            if "SET EVENT_URL" in sql_u:
                new_url, row_id = params
                for r in self.event_groups:
                    if r["id"] == row_id:
                        r["event_url"] = new_url
                        return None
            if "SET TOTAL_COUNT = TOTAL_COUNT + 1" in sql_u:
                # (now, title, reason, source, sentiment_id, id)
                now, title, reason, source, sentiment_id, row_id = params
                for r in self.event_groups:
                    if r["id"] == row_id:
                        r["total_count"] = int(r.get("total_count") or 0) + 1
                        r["last_seen_at"] = now
                        r["last_title"] = title
                        r["last_reason"] = reason
                        r["last_source"] = source
                        r["last_sentiment_id"] = sentiment_id
                        return None
            return None

        raise AssertionError(f"FakeDB got unexpected SQL: {sql!r} params={params!r}")

    def execute_with_lastrowid(self, project_root, sql, params=None):
        params = params or ()
        sql_u = " ".join((sql or "").split()).upper()
        if not sql_u.startswith("INSERT INTO EVENT_GROUPS"):
            raise AssertionError(f"FakeDB got unexpected INSERT: {sql!r}")

        (
            hospital_name,
            fingerprint,
            event_url,
            last_title,
            last_reason,
            last_source,
            last_sentiment_id,
            created_at,
            last_seen_at,
        ) = params

        row_id = self._next_id
        self._next_id += 1
        self.event_groups.append(
            {
                "id": row_id,
                "hospital_name": hospital_name,
                "fingerprint": int(fingerprint),
                "event_url": event_url,
                "total_count": 1,
                "last_title": last_title,
                "last_reason": last_reason,
                "last_source": last_source,
                "last_sentiment_id": last_sentiment_id,
                "created_at": created_at,
                "last_seen_at": last_seen_at,
            }
        )
        return row_id


class EventDedupeTests(unittest.TestCase):
    def _make_monitor(self):
        # Import lazily so sys.path tweak above applies.
        import main as mail_main  # type: ignore

        m = mail_main.SentimentMonitor.__new__(mail_main.SentimentMonitor)
        m.project_root = str(ROOT)
        m.config = {
            "runtime": {
                "event_dedupe": {
                    "enabled": True,
                    "window_days": 7,
                    "max_distance": 4,
                }
            }
        }
        m._now_local_str = lambda: "2026-02-06 22:32:39"
        return mail_main, m

    def test_duplicate_detected_even_if_ai_reason_differs(self):
        mail_main, m = self._make_monitor()
        fake_db = _FakeDB()

        # Monkeypatch the imported db module inside main.py
        old_db = mail_main.db
        mail_main.db = fake_db
        try:
            sentiment_1 = {
                "id": "2461163801",
                "webName": "抖音",
                "title": "医院出来的路好黑啊，哈哈哈，明明处理过了我偷偷地又给扯开，好多🩸",
                "allContent": "医院出来的路好黑啊，哈哈哈，明明处理过了我偷偷地又给扯开，好多🩸",
                "ocrData": "",
                "url": "https://www.douyin.com/share/video/7600000000000000000?foo=bar",
            }
            analysis_1 = {"is_negative": True, "reason": "理由A", "severity": "low"}

            event_id_1, is_dup_1, total_1 = m._match_or_create_event(sentiment_1, "东莞市滨海湾中心医院", analysis_1)
            self.assertIsNotNone(event_id_1)
            self.assertFalse(is_dup_1)
            self.assertEqual(total_1, 1)

            sentiment_2 = dict(sentiment_1)
            sentiment_2["id"] = "2461164619"
            analysis_2 = {"is_negative": True, "reason": "理由B（不同）", "severity": "low"}

            event_id_2, is_dup_2, total_2 = m._match_or_create_event(sentiment_2, "东莞市滨海湾中心医院", analysis_2)
            self.assertEqual(event_id_2, event_id_1)
            self.assertTrue(is_dup_2)
            self.assertEqual(total_2, 2)
        finally:
            mail_main.db = old_db

    def test_normalize_douyin_share_and_video_same_key(self):
        mail_main, m = self._make_monitor()
        k1 = m._normalize_event_url("https://www.douyin.com/share/video/7599293256921227897", "抖音")
        k2 = m._normalize_event_url("https://www.douyin.com/video/7599293256921227897?previous_page=app_code_link", "抖音")
        self.assertEqual(k1, "douyin:7599293256921227897")
        self.assertEqual(k2, "douyin:7599293256921227897")


if __name__ == "__main__":
    unittest.main()

