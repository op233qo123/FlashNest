#!/usr/bin/env python3
"""Validate native localization parity, formatting contracts and source key coverage."""
import json
import pathlib
import re
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]

def strings(language):
    path = ROOT / 'App/Resources/Localization' / (language + '.lproj') / 'Localizable.strings'
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('//'):
            continue
        match = re.fullmatch(r'("(?:[^"\\]|\\.)*")\s*=\s*("(?:[^"\\]|\\.)*");', line)
        if not match:
            raise AssertionError(f'Invalid strings syntax: {path}: {line}')
        key, value = map(json.loads, match.groups())
        if key in result:
            raise AssertionError(f'Duplicate key {key} in {path}')
        result[key] = value
    return result

class LocalizationTests(unittest.TestCase):
    def test_complete_matching_languages(self):
        en, zh = strings('en'), strings('zh-Hans')
        self.assertEqual(en.keys(), zh.keys())
        self.assertGreater(len(en), 70)
        for key in en:
            self.assertTrue(en[key] and zh[key], key)
            self.assertEqual(re.findall(r'%(?:\d+\$)?(?:ll|l)?[df@]', en[key]), re.findall(r'%(?:\d+\$)?(?:ll|l)?[df@]', zh[key]), key)

    def test_literal_native_keys_exist(self):
        keys = strings('en')
        for source in (ROOT / 'App').rglob('*.swift'):
            for match in re.finditer(r'L10n\.(?:text|format)\("([^"\\]*)"\s*[,)]', source.read_text()):
                self.assertIn(match[1], keys, f'{source}: {match[1]}')

    def test_language_preference_is_scoped(self):
        helper = (ROOT / 'App/Localization/L10n.swift').read_text()
        self.assertIn('FlashNest.language', helper)
        self.assertIn('Locale.preferredLanguages', helper)
        self.assertNotIn('forKey: "AppleLanguages"', helper)

if __name__ == '__main__':
    unittest.main()
