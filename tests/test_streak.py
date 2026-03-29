"""Pure unit tests for the streak evaluation function."""

from datetime import date

from app.services.streak import StreakResult, evaluate_streak


class TestFirstCompletion:

    def test_first_completion(self):
        result = evaluate_streak("daily", 0, 0, None, date(2026, 3, 25))
        assert result == StreakResult(current_streak=1, best_streak=1, streak_was_broken=False)

    def test_first_completion_preserves_best(self):
        result = evaluate_streak("daily", 0, 5, None, date(2026, 3, 25))
        assert result.best_streak == 5


class TestDailyFrequency:

    def test_consecutive_days(self):
        result = evaluate_streak("daily", 3, 3, date(2026, 3, 24), date(2026, 3, 25))
        assert result == StreakResult(current_streak=4, best_streak=4, streak_was_broken=False)

    def test_skip_one_day(self):
        result = evaluate_streak("daily", 5, 5, date(2026, 3, 23), date(2026, 3, 25))
        assert result == StreakResult(current_streak=1, best_streak=5, streak_was_broken=True)


class TestWeekdayFrequency:

    def test_thu_to_fri(self):
        # Thursday to Friday — 1 weekday
        result = evaluate_streak("weekdays", 2, 2, date(2026, 3, 19), date(2026, 3, 20))
        assert result.current_streak == 3
        assert result.streak_was_broken is False

    def test_fri_to_mon(self):
        # Friday to Monday — skips weekend, 1 weekday
        result = evaluate_streak("weekdays", 4, 4, date(2026, 3, 20), date(2026, 3, 23))
        assert result.current_streak == 5
        assert result.streak_was_broken is False

    def test_fri_to_tue(self):
        # Friday to Tuesday — missed Monday, 2 weekdays
        result = evaluate_streak("weekdays", 4, 4, date(2026, 3, 20), date(2026, 3, 24))
        assert result == StreakResult(current_streak=1, best_streak=4, streak_was_broken=True)


class TestWeekendFrequency:

    def test_sat_to_sun(self):
        # Saturday to Sunday — 1 weekend day
        result = evaluate_streak("weekends", 2, 2, date(2026, 3, 21), date(2026, 3, 22))
        assert result.current_streak == 3
        assert result.streak_was_broken is False

    def test_sun_to_sat(self):
        # Sunday to next Saturday — skips weekdays, 1 weekend day
        result = evaluate_streak("weekends", 1, 1, date(2026, 3, 22), date(2026, 3, 28))
        assert result.current_streak == 2
        assert result.streak_was_broken is False

    def test_sun_to_next_sun(self):
        # Sunday to next Sunday — missed Saturday, 2 weekend days
        result = evaluate_streak("weekends", 3, 3, date(2026, 3, 22), date(2026, 3, 29))
        assert result == StreakResult(current_streak=1, best_streak=3, streak_was_broken=True)


class TestWeeklyFrequency:

    def test_within_7_days(self):
        result = evaluate_streak("weekly", 2, 2, date(2026, 3, 18), date(2026, 3, 25))
        assert result.current_streak == 3
        assert result.streak_was_broken is False

    def test_exactly_7_days(self):
        result = evaluate_streak("weekly", 1, 1, date(2026, 3, 18), date(2026, 3, 25))
        assert result.current_streak == 2
        assert result.streak_was_broken is False

    def test_8_day_gap(self):
        result = evaluate_streak("weekly", 5, 5, date(2026, 3, 17), date(2026, 3, 25))
        assert result == StreakResult(current_streak=1, best_streak=5, streak_was_broken=True)


class TestCustomFrequency:

    def test_mwf_mon_to_wed(self):
        # Mon/Wed/Fri: max gap is 3 (Fri→Mon). Mon→Wed = 2 days, within max gap.
        result = evaluate_streak(
            "custom", 2, 2, date(2026, 3, 23), date(2026, 3, 25),
            scheduled_days=[0, 2, 4],
        )
        assert result.current_streak == 3
        assert result.streak_was_broken is False

    def test_mwf_mon_to_sat(self):
        # Mon→Sat = 5 days, exceeds max gap of 3.
        result = evaluate_streak(
            "custom", 2, 2, date(2026, 3, 23), date(2026, 3, 28),
            scheduled_days=[0, 2, 4],
        )
        assert result == StreakResult(current_streak=1, best_streak=2, streak_was_broken=True)

    def test_no_schedules_falls_back_to_weekly(self):
        result = evaluate_streak(
            "custom", 1, 1, date(2026, 3, 18), date(2026, 3, 25),
            scheduled_days=[],
        )
        assert result.current_streak == 2
        assert result.streak_was_broken is False

    def test_single_scheduled_day_weekly(self):
        # Only one day scheduled — treated as weekly (gap=7)
        result = evaluate_streak(
            "custom", 1, 1, date(2026, 3, 18), date(2026, 3, 25),
            scheduled_days=[2],
        )
        assert result.current_streak == 2


class TestEdgeCases:

    def test_same_day_duplicate(self):
        result = evaluate_streak("daily", 3, 5, date(2026, 3, 25), date(2026, 3, 25))
        assert result == StreakResult(current_streak=3, best_streak=5, streak_was_broken=False)

    def test_backdate(self):
        result = evaluate_streak("daily", 3, 5, date(2026, 3, 25), date(2026, 3, 24))
        assert result == StreakResult(current_streak=3, best_streak=5, streak_was_broken=False)

    def test_best_streak_updates(self):
        result = evaluate_streak("daily", 5, 5, date(2026, 3, 24), date(2026, 3, 25))
        assert result.current_streak == 6
        assert result.best_streak == 6

    def test_best_streak_does_not_decrease(self):
        result = evaluate_streak("daily", 2, 10, date(2026, 3, 22), date(2026, 3, 25))
        assert result.current_streak == 1
        assert result.best_streak == 10
