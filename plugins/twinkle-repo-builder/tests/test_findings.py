import unittest

from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding, Report


class TestFinding(unittest.TestCase):
    def test_link_gate_classes_are_closed(self):
        """Семь классов секции 13 плюс два, заведённых под наблюдённые поломки.

        `undecodable` — вместо чтения с заменой байта, называвшего цель
        `[[???????]]`, которой никто не писал. `broad-allow` — вместо
        запрета одного лишь синтаксиса подстроки: `*a*` гасит по всему
        репозиторию и при этом считается использованной. Оба расхождения
        со спекой вынесены автору (незыблемое №7).
        """
        from scripts.findings import LINK_CLASSES
        self.assertEqual(
            set(LINK_CLASSES),
            {"unresolved", "md-link-to-file", "link-to-transient",
             "escapes-root", "dead-allow", "broad-allow", "ambiguous",
             "orphan", "undecodable"},
        )

    def test_severity_is_a_property_of_the_class_not_the_caller(self):
        from scripts.findings import severity
        self.assertEqual(severity("unresolved"), "error")
        self.assertEqual(severity("escapes-root"), "error")
        self.assertEqual(severity("dead-allow"), "error")
        self.assertEqual(severity("broad-allow"), "error")
        self.assertEqual(severity("ambiguous"), "warning")
        self.assertEqual(severity("orphan"), "report")

    def test_an_unreadable_file_is_an_error_not_a_softer_verdict(self):
        """Понизить тяжесть заодно с починкой правдивости — ослабить гейт.

        Класс заведён взамен подстановки замещающего знака, которая давала
        `unresolved`, то есть ошибку. И по существу: ссылки такого файла
        не проверил никто, а прогон с непроверенным куском дерева зелёным
        быть не может.
        """
        from scripts.findings import severity
        self.assertEqual(severity("undecodable"), "error")
        self.assertEqual(
            Report([Finding("undecodable", "core/a.md", 1, "x")]).exit_code(),
            EXIT_VIOLATION)


class TestAdoptClasses(unittest.TestCase):
    def test_the_wave_carries_exactly_these_seven(self):
        from scripts import findings
        self.assertEqual(list(findings.ADOPT_CLASSES), [
            "plan-unparseable",
            "uncovered-path",
            "overlapping-line",
            "unagreed-change",
            "line-state-conflict",
            "foreign-repo",
            "created-unrecoverable",
        ])

    def test_five_are_errors_and_two_are_reports(self):
        """Отчёт — не смягчение: `foreign-repo` и `created-unrecoverable`
        сообщают о свойствах чужого дерева, а не о нарушении процедуры.
        Ошибкой их сделать значило бы объявить чужое дерево виноватым."""
        from scripts import findings
        by_severity = {}
        for cls in findings.ADOPT_CLASSES:
            by_severity.setdefault(findings.severity(cls), []).append(cls)
        self.assertEqual(sorted(by_severity), ["error", "report"])
        self.assertEqual(sorted(by_severity["report"]),
                         ["created-unrecoverable", "foreign-repo"])


class TestMaintainClasses(unittest.TestCase):
    def test_the_wave_carries_exactly_these_ten(self):
        from scripts import findings
        self.assertEqual(list(findings.MAINTAIN_CLASSES), [
            "content-modified",
            "unexplained-count",
            "silent-substitution",
            "structure-without-content",
            "empty-collection",
            "declared-unused",
            "view-selects-nothing",
            "map-tree-divergence",
            "archetype-mismatch",
            "unreferenced-ignored-binary",
        ])

    def test_four_are_errors_and_six_are_reports(self):
        """Ошибка — про нарушенное обещание плагина о себе. Отчёт — про
        наблюдение о дереве, которое чинить не плагину."""
        from scripts import findings
        by_severity = {}
        for cls in findings.MAINTAIN_CLASSES:
            by_severity.setdefault(findings.severity(cls), []).append(cls)
        self.assertEqual(sorted(by_severity), ["error", "report"])
        self.assertEqual(sorted(by_severity["error"]), [
            "content-modified", "silent-substitution",
            "structure-without-content", "unexplained-count"])
        self.assertEqual(len(by_severity["report"]), 6)

    def test_no_class_named_demand_acted_on_exists(self):
        """Соблазн есть: имя выглядит как гарантия. Производителя у него в
        бою нет — это утверждение теста, — а имя без стоящего за ним
        поведения волна 1 уже оплачивала (`EXIT_TOOL_FAILED`)."""
        from scripts import findings
        self.assertNotIn("demand-acted-on", findings.MAINTAIN_CLASSES)


class TestReportDeterminism(unittest.TestCase):
    def test_same_findings_in_any_order_render_identically(self):
        a = Finding("unresolved", "areas/b.md", 12, "[[nope]]")
        b = Finding("md-link-to-file", "areas/a.md", 3, "[x](y.md)")
        self.assertEqual(Report([a, b]).render(), Report([b, a]).render())

    def test_render_has_no_absolute_paths(self):
        r = Report([Finding("unresolved", "areas/b.md", 12, "[[nope]]")]).render()
        self.assertNotIn("/Users/", r)
        self.assertTrue(r.startswith("areas/b.md:12"), r)

    def test_exit_code_is_violation_only_for_errors(self):
        self.assertEqual(Report([]).exit_code(), EXIT_OK)
        self.assertEqual(Report([Finding("ambiguous", "a.md", 1, "x")]).exit_code(), EXIT_OK)
        self.assertEqual(Report([Finding("orphan", "a.md", 1, "x")]).exit_code(), EXIT_OK)
        self.assertEqual(
            Report([Finding("unresolved", "a.md", 1, "x")]).exit_code(), EXIT_VIOLATION
        )

    def test_counts_by_class_are_what_tests_assert_against(self):
        r = Report([
            Finding("unresolved", "a.md", 1, "x"),
            Finding("unresolved", "b.md", 2, "y"),
            Finding("ambiguous", "c.md", 3, "z"),
        ])
        self.assertEqual(r.counts(), {"unresolved": 2, "ambiguous": 1})
