#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_ROOT / 'scripts'

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location('bdc_client_test', SCRIPT_DIR / 'client.py')
assert spec and spec.loader
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

from _bdc_env import resolve_bdc_env  # type: ignore  # noqa: E402
from _http_json import HttpResult  # type: ignore  # noqa: E402


class DevtoolsSkillCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / '.env'
        self.env_path.write_text(
            'BENSZ_CHANNEL_URL=http://127.0.0.1:6542\n'
            'BENSZ_CHANNEL_KEY=bdc_xxxxxxxxxxxxxxxxxxxxxxxx\n',
            encoding='utf-8',
        )
        self.env = resolve_bdc_env(skill_root=SKILL_ROOT, env_file=self.env_path)
        self.original_dry_run = client.DRY_RUN

    def tearDown(self) -> None:
        client.DRY_RUN = self.original_dry_run
        self.temp_dir.cleanup()

    def invoke_cli(self, *argv: str):
        records: list[dict[str, object]] = []
        with patch.object(client, '_print_json', side_effect=records.append):
            rc = client.main(['--env', str(self.env_path), '--dry-run', *argv])
        return rc, records

    def find_request(self, records: list[dict[str, object]], method: str, path_fragment: str) -> dict[str, object]:
        for record in records:
            if record.get('method') == method and path_fragment in str(record.get('url', '')):
                return record
        self.fail(f'未找到请求: method={method}, path_fragment={path_fragment}, records={records!r}')

    def test_channels_create_supports_show_in_top_nav_flag(self) -> None:
        rc, records = self.invoke_cli(
            'channels', 'create',
            '--name', '公告',
            '--icon', '📢',
            '--accent-color', '#3b82f6',
            '--show-in-top-nav', 'false',
        )
        self.assertEqual(rc, 0)
        request = self.find_request(records, 'POST', '/api/vibe/channels')
        self.assertEqual(request['json_body']['show_in_top_nav'], False)

    def test_articles_list_supports_tag_filter(self) -> None:
        rc, records = self.invoke_cli(
            'articles', 'list',
            '--channel-id', '3',
            '--published', 'false',
            '--pinned', 'true',
            '--featured', 'false',
            '--tag-id', '12',
        )
        self.assertEqual(rc, 0)
        request = self.find_request(records, 'GET', '/api/vibe/articles')
        url = str(request['url'])
        self.assertIn('channel_id=3', url)
        self.assertIn('published=false', url)
        self.assertIn('pinned=true', url)
        self.assertIn('featured=false', url)
        self.assertIn('tag_id=12', url)

    def test_articles_create_supports_tag_ids(self) -> None:
        rc, records = self.invoke_cli(
            'articles', 'create',
            '--channel-id', '9',
            '--title', '带标签文章',
            '--body', '正文',
            '--published',
            '--tag-id', '2',
            '--tag-id', '7',
        )
        self.assertEqual(rc, 0)
        request = self.find_request(records, 'POST', '/api/vibe/articles')
        self.assertEqual(request['json_body']['tag_ids'], [2, 7])
        self.assertTrue(str(request['headers'].get('x-idempotency-key', '')).startswith('bdc-article-create-v1-'))
        self.assertEqual(request['retries'], 2)

    def test_articles_create_draft_is_forced_to_stay_unpublished_for_verification(self) -> None:
        rc, records = self.invoke_cli(
            'articles', 'create-draft',
            '--channel-id', '9',
            '--title', '验证草稿',
            '--body', '正文',
            '--tag-id', '2',
            '--tag-id', '7',
        )
        self.assertEqual(rc, 0)
        request = self.find_request(records, 'POST', '/api/vibe/articles')
        self.assertEqual(request['json_body']['tag_ids'], [2, 7])
        self.assertEqual(request['json_body']['is_published'], False)
        self.assertEqual(request['json_body']['is_pinned'], False)
        self.assertEqual(request['json_body']['is_featured'], False)
        self.assertNotIn('published_at', request['json_body'])
        self.assertTrue(str(request['headers'].get('x-idempotency-key', '')).startswith('bdc-article-create-v1-'))
        self.assertEqual(request['retries'], 2)

    def test_articles_create_auto_idempotency_key_is_deterministic_for_same_payload(self) -> None:
        rc1, records1 = self.invoke_cli(
            'articles', 'create',
            '--channel-id', '9',
            '--title', '稳定幂等测试',
            '--body', '正文',
            '--published',
            '--tag-id', '2',
            '--tag-id', '7',
        )
        rc2, records2 = self.invoke_cli(
            'articles', 'create',
            '--channel-id', '9',
            '--title', '稳定幂等测试',
            '--body', '正文',
            '--published',
            '--tag-id', '2',
            '--tag-id', '7',
        )

        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        request1 = self.find_request(records1, 'POST', '/api/vibe/articles')
        request2 = self.find_request(records2, 'POST', '/api/vibe/articles')
        self.assertEqual(
            request1['headers'].get('x-idempotency-key'),
            request2['headers'].get('x-idempotency-key'),
        )

    def test_articles_create_supports_custom_idempotency_key(self) -> None:
        rc, records = self.invoke_cli(
            'articles', 'create',
            '--channel-id', '9',
            '--title', '自定义幂等键',
            '--body', '正文',
            '--published',
            '--idempotency-key', 'manual-key-001',
        )
        self.assertEqual(rc, 0)
        request = self.find_request(records, 'POST', '/api/vibe/articles')
        self.assertEqual(request['headers'].get('x-idempotency-key'), 'manual-key-001')

    def test_articles_update_supports_clear_tags(self) -> None:
        rc, records = self.invoke_cli(
            'articles', 'update',
            '--id', 'article-42',
            '--title', '清空标签',
            '--clear-tags',
        )
        self.assertEqual(rc, 0)
        request = self.find_request(records, 'PUT', '/api/vibe/articles/article-42')
        self.assertEqual(request['json_body']['tag_ids'], [])
        self.assertEqual(request['retries'], 0)

    def test_articles_update_rejects_mixed_tag_modes(self) -> None:
        with self.assertRaises(SystemExit):
            client.main([
                '--env', str(self.env_path),
                '--dry-run',
                'articles', 'update',
                '--id', 'article-42',
                '--tag-id', '2',
                '--clear-tags',
            ])

    def test_tags_crud_commands_are_available(self) -> None:
        rc, records = self.invoke_cli(
            'tags', 'create',
            '--name', 'Laravel',
            '--slug', 'laravel',
            '--description', 'Laravel 标签',
        )
        self.assertEqual(rc, 0)
        create_request = self.find_request(records, 'POST', '/api/vibe/tags')
        self.assertEqual(create_request['json_body']['name'], 'Laravel')
        self.assertEqual(create_request['json_body']['slug'], 'laravel')
        self.assertEqual(create_request['retries'], 0)

        rc, records = self.invoke_cli(
            'tags', 'update',
            '--id', 'laravel',
            '--name', 'Laravel 12',
        )
        self.assertEqual(rc, 0)
        update_request = self.find_request(records, 'PUT', '/api/vibe/tags/laravel')
        self.assertEqual(update_request['json_body']['name'], 'Laravel 12')
        self.assertEqual(update_request['retries'], 0)

        rc, records = self.invoke_cli('tags', 'delete', '--id', 'tag-public-id')
        self.assertEqual(rc, 0)
        delete_request = self.find_request(records, 'DELETE', '/api/vibe/tags/tag-public-id')
        self.assertEqual(delete_request['method'], 'DELETE')
        self.assertEqual(delete_request['retries'], 0)

    def test_tags_ensure_reuses_existing_tag_before_creating(self) -> None:
        client.DRY_RUN = False
        requests: list[tuple[str, str, object | None]] = []
        outputs: list[dict[str, object]] = []

        def fake_call(method: str, url: str, *, json_body: object | None = None, **_: object) -> HttpResult:
            requests.append((method, url, json_body))

            if method == 'GET' and url.endswith('/api/vibe/tags'):
                return HttpResult(
                    status=200,
                    headers={},
                    body_text='{"data":[{"id":7,"name":"Laravel","slug":"laravel","public_id":"tag_a1b2c3d4"}]}',
                    json={'data': [{'id': 7, 'name': 'Laravel', 'slug': 'laravel', 'public_id': 'tag_a1b2c3d4'}]},
                )

            raise AssertionError(f'未预期请求: {method} {url}')

        with patch.object(client, '_call', side_effect=fake_call), patch.object(client, '_print_json', side_effect=outputs.append):
            rc = client.cmd_tags_ensure(self.env, 5, 'Laravel', None, 'Laravel 相关文章')

        self.assertEqual(rc, 0)
        self.assertEqual(len(requests), 1)
        self.assertEqual(outputs[0]['action'], 'reuse_existing_tag')
        self.assertEqual(outputs[0]['matched_by'], 'name')
        self.assertEqual(outputs[0]['tag']['id'], 7)

    def test_tags_ensure_creates_new_tag_when_no_existing_match(self) -> None:
        client.DRY_RUN = False
        requests: list[tuple[str, str, object | None]] = []

        def fake_call(method: str, url: str, *, json_body: object | None = None, **_: object) -> HttpResult:
            requests.append((method, url, json_body))

            if method == 'GET' and url.endswith('/api/vibe/tags'):
                return HttpResult(status=200, headers={}, body_text='{"data":[]}', json={'data': []})

            if method == 'POST' and url.endswith('/api/vibe/connect'):
                return HttpResult(status=200, headers={}, body_text='{"connectionId":"conn-1"}', json={'connectionId': 'conn-1'})

            if method == 'POST' and url.endswith('/api/vibe/tags'):
                return HttpResult(
                    status=201,
                    headers={},
                    body_text='{"tag":{"id":11,"name":"New Tag","slug":"new-tag"}}',
                    json={'tag': {'id': 11, 'name': 'New Tag', 'slug': 'new-tag'}},
                )

            if method == 'POST' and url.endswith('/api/vibe/disconnect'):
                return HttpResult(status=200, headers={}, body_text='{"ok":true}', json={'ok': True})

            raise AssertionError(f'未预期请求: {method} {url}')

        with patch.object(client, '_call', side_effect=fake_call), patch.object(client, '_print_json', side_effect=lambda *_args, **_kwargs: None):
            rc = client.cmd_tags_ensure(self.env, 5, 'New Tag', 'new-tag', '新的标签')

        self.assertEqual(rc, 0)
        self.assertEqual(sum(1 for method, url, _body in requests if method == 'GET' and url.endswith('/api/vibe/tags')), 1)
        self.assertEqual(sum(1 for method, url, _body in requests if method == 'POST' and url.endswith('/api/vibe/connect')), 1)
        self.assertEqual(sum(1 for method, url, _body in requests if method == 'POST' and url.endswith('/api/vibe/tags')), 1)
        self.assertEqual(sum(1 for method, url, _body in requests if method == 'POST' and url.endswith('/api/vibe/disconnect')), 1)

    def test_tags_ensure_reuses_tag_after_create_conflict(self) -> None:
        client.DRY_RUN = False
        requests: list[tuple[str, str, object | None]] = []
        outputs: list[dict[str, object]] = []
        tag_list_calls = 0

        def fake_call(method: str, url: str, *, json_body: object | None = None, **_: object) -> HttpResult:
            nonlocal tag_list_calls
            requests.append((method, url, json_body))

            if method == 'GET' and url.endswith('/api/vibe/tags'):
                tag_list_calls += 1
                if tag_list_calls == 1:
                    return HttpResult(status=200, headers={}, body_text='{"data":[]}', json={'data': []})
                return HttpResult(
                    status=200,
                    headers={},
                    body_text='{"data":[{"id":9,"name":"Laravel","slug":"laravel","public_id":"tag_z9y8x7w6"}]}',
                    json={'data': [{'id': 9, 'name': 'Laravel', 'slug': 'laravel', 'public_id': 'tag_z9y8x7w6'}]},
                )

            if method == 'POST' and url.endswith('/api/vibe/connect'):
                return HttpResult(status=200, headers={}, body_text='{"connectionId":"conn-1"}', json={'connectionId': 'conn-1'})

            if method == 'POST' and url.endswith('/api/vibe/tags'):
                return HttpResult(
                    status=422,
                    headers={},
                    body_text='{"message":"The name has already been taken."}',
                    json={'message': 'The name has already been taken.'},
                )

            if method == 'POST' and url.endswith('/api/vibe/disconnect'):
                return HttpResult(status=200, headers={}, body_text='{"ok":true}', json={'ok': True})

            raise AssertionError(f'未预期请求: {method} {url}')

        with patch.object(client, '_call', side_effect=fake_call), patch.object(client, '_print_json', side_effect=outputs.append):
            rc = client.cmd_tags_ensure(self.env, 5, 'Laravel', 'laravel', 'Laravel 相关文章')

        self.assertEqual(rc, 0)
        self.assertEqual(tag_list_calls, 2)
        self.assertEqual(outputs[-1]['action'], 'reuse_existing_tag_after_conflict')
        self.assertEqual(outputs[-1]['tag']['id'], 9)

    def test_tags_ensure_cli_is_available_in_dry_run_mode(self) -> None:
        rc, records = self.invoke_cli(
            'tags', 'ensure',
            '--name', 'Laravel',
            '--slug', 'laravel',
            '--description', 'Laravel 标签',
        )
        self.assertEqual(rc, 0)
        list_request = self.find_request(records, 'GET', '/api/vibe/tags')
        self.assertEqual(list_request['method'], 'GET')
        ensure_summary = next(record for record in records if record.get('action') == 'create_tag_if_needed')
        self.assertEqual(ensure_summary['name'], 'Laravel')
        self.assertEqual(ensure_summary['slug'], 'laravel')

    def test_tags_commands_use_connection_lifecycle_in_live_mode(self) -> None:
        client.DRY_RUN = False
        requests: list[tuple[str, str, object | None]] = []

        def fake_call(method: str, url: str, *, json_body: object | None = None, **_: object) -> HttpResult:
            requests.append((method, url, json_body))

            if method == 'GET' and url.endswith('/api/vibe/tags'):
                return HttpResult(status=200, headers={}, body_text='{"data":[]}', json={'data': []})

            if method == 'POST' and url.endswith('/api/vibe/connect'):
                return HttpResult(status=200, headers={}, body_text='{"connectionId":"conn-1"}', json={'connectionId': 'conn-1'})

            if method == 'POST' and url.endswith('/api/vibe/tags'):
                return HttpResult(status=201, headers={}, body_text='{"tag":{"id":1}}', json={'tag': {'id': 1}})

            if method == 'PUT' and url.endswith('/api/vibe/tags/laravel'):
                return HttpResult(status=200, headers={}, body_text='{"tag":{"slug":"laravel"}}', json={'tag': {'slug': 'laravel'}})

            if method == 'DELETE' and url.endswith('/api/vibe/tags/laravel'):
                return HttpResult(status=200, headers={}, body_text='{"ok":true}', json={'ok': True})

            if method == 'POST' and url.endswith('/api/vibe/disconnect'):
                return HttpResult(status=200, headers={}, body_text='{"ok":true}', json={'ok': True})

            raise AssertionError(f'未预期请求: {method} {url}')

        with patch.object(client, '_call', side_effect=fake_call), patch.object(client, '_print_json', side_effect=lambda *_args, **_kwargs: None):
            self.assertEqual(client.cmd_tags_list(self.env, 5), 0)
            self.assertEqual(client.cmd_tags_create(self.env, 5, 'Laravel', 'laravel', 'Laravel 标签'), 0)
            self.assertEqual(client.cmd_tags_update(self.env, 5, 'laravel', name='Laravel 12'), 0)
            self.assertEqual(client.cmd_tags_delete(self.env, 5, 'laravel'), 0)

        connect_count = sum(1 for method, url, _body in requests if method == 'POST' and url.endswith('/api/vibe/connect'))
        disconnect_count = sum(1 for method, url, _body in requests if method == 'POST' and url.endswith('/api/vibe/disconnect'))
        self.assertEqual(connect_count, 3)
        self.assertEqual(disconnect_count, 3)

    def test_users_update_supports_avatar_url(self) -> None:
        rc, records = self.invoke_cli(
            'users', 'update',
            '--id', '7',
            '--role', 'admin',
            '--avatar-url', 'https://cdn.example.com/avatar.png',
        )
        self.assertEqual(rc, 0)
        request = self.find_request(records, 'PUT', '/api/vibe/users/7')
        self.assertEqual(request['json_body']['role'], 'admin')
        self.assertEqual(request['json_body']['avatar_url'], 'https://cdn.example.com/avatar.png')
        self.assertEqual(request['retries'], 0)

    def test_doctor_returns_failure_when_heartbeat_is_not_ok(self) -> None:
        client.DRY_RUN = False

        def fake_call(method: str, url: str, **_: object) -> HttpResult:
            if url.endswith('/api/vibe/ping'):
                return HttpResult(status=200, headers={}, body_text='{"ok":true}', json={'ok': True})
            if url.endswith('/api/vibe/connect'):
                return HttpResult(status=200, headers={}, body_text='{"connectionId":"conn-1"}', json={'connectionId': 'conn-1'})
            if url.endswith('/api/vibe/heartbeat'):
                return HttpResult(status=500, headers={}, body_text='{"error":"boom"}', json={'error': 'boom'})
            if url.endswith('/api/vibe/disconnect'):
                return HttpResult(status=200, headers={}, body_text='{"ok":true}', json={'ok': True})
            raise AssertionError(f'未预期请求: {method} {url}')

        with patch.object(client, '_call', side_effect=fake_call), patch.object(client, '_print_json', side_effect=lambda *_args, **_kwargs: None):
            rc = client.cmd_doctor(self.env, 5)

        self.assertEqual(rc, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
