import datetime
import unittest

from rain_logic import get_timezone, is_in_notification_window, parse_pause_duration, parse_stored_datetime


class PauseDurationTests(unittest.TestCase):
    def test_minutes_are_the_default(self):
        self.assertEqual(parse_pause_duration("30"), datetime.timedelta(minutes=30))

    def test_supported_units(self):
        self.assertEqual(parse_pause_duration("30m"), datetime.timedelta(minutes=30))
        self.assertEqual(parse_pause_duration("2H"), datetime.timedelta(hours=2))
        self.assertEqual(parse_pause_duration("1d"), datetime.timedelta(days=1))

    def test_invalid_or_unbounded_duration_is_rejected(self):
        for value in ("0", "8d", "1.5h", "tomorrow", "-30"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_pause_duration(value)


class NotificationWindowTests(unittest.TestCase):
    def test_daytime_window(self):
        self.assertTrue(is_in_notification_window(datetime.datetime(2026, 1, 1, 8), 8, 22))
        self.assertFalse(is_in_notification_window(datetime.datetime(2026, 1, 1, 22), 8, 22))

    def test_overnight_window(self):
        self.assertTrue(is_in_notification_window(datetime.datetime(2026, 1, 1, 23), 22, 6))
        self.assertTrue(is_in_notification_window(datetime.datetime(2026, 1, 1, 5), 22, 6))
        self.assertFalse(is_in_notification_window(datetime.datetime(2026, 1, 1, 12), 22, 6))

    def test_equal_hours_mean_all_day(self):
        self.assertTrue(is_in_notification_window(datetime.datetime(2026, 1, 1, 12), 8, 8))


class StoredDatetimeTests(unittest.TestCase):
    def test_datetime_is_normalized_to_utc(self):
        value = parse_stored_datetime("2026-01-01T09:00:00+09:00")
        self.assertEqual(value, datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc))

    def test_invalid_value_is_ignored(self):
        self.assertIsNone(parse_stored_datetime("not-a-date"))
        self.assertIsNone(parse_stored_datetime(None))


class TimezoneTests(unittest.TestCase):
    def test_tokyo_timezone_is_available(self):
        self.assertEqual(get_timezone("Asia/Tokyo").key, "Asia/Tokyo")


if __name__ == "__main__":
    unittest.main()
