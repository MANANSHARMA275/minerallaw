"""
Tests for the Legislation / Rule-Change Digest feature:
  - Public /legislation page: no login required, hides unpublished, shows published,
    respects display_order.
  - Admin access control: non-superadmin gets 403 on list and create.
  - Admin CRUD: superadmin can create, toggle, delete; CSRF is enforced on create;
    AuditLog is written; missing required fields return 400.
"""
import pytest

from app import db
from app.models import AuditLog, Legislation, User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(phone, role='user'):
    u = User(phone=phone, role=role, subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, app, user):
    app.login_manager.session_protection = None
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_entry(title='Test Entry', category='2025 Amendment',
                is_published=False, display_order=0, **kwargs):
    e = Legislation(
        title=title, category=category,
        is_published=is_published, display_order=display_order,
        **kwargs,
    )
    db.session.add(e)
    db.session.commit()
    return e


def _post_create(client, **form):
    data = {
        'title': 'Entry Title',
        'category': '2025 Amendment',
        'summary_en': 'English summary.',
        'display_order': '0',
    }
    data.update(form)
    return client.post('/admin/legislation/create', data=data)


# ── Public page ───────────────────────────────────────────────────────────────

class TestLegislationPublicPage:

    def test_public_page_returns_200_without_login(self, client):
        """GET /legislation must be accessible to anonymous users."""
        resp = client.get('/legislation')
        assert resp.status_code == 200

    def test_public_page_hides_unpublished(self, app, client):
        """Unpublished entries must not appear in the page HTML."""
        _make_entry(title='Hidden Entry', is_published=False)
        resp = client.get('/legislation')
        assert b'Hidden Entry' not in resp.data

    def test_public_page_shows_published(self, app, client):
        """Published entries must appear in the page HTML."""
        _make_entry(title='Visible Entry', is_published=True)
        resp = client.get('/legislation')
        assert b'Visible Entry' in resp.data

    def test_public_page_empty_state_when_no_published(self, app, client):
        """When nothing is published, the empty-state message must appear."""
        _make_entry(title='Only Unpublished', is_published=False)
        resp = client.get('/legislation')
        body = resp.data.decode()
        assert 'No legislation entries published yet' in body

    def test_display_order_respected(self, app, client):
        """Lower display_order entry must appear before higher one in HTML."""
        _make_entry(title='Second', category='Fees', is_published=True, display_order=2)
        _make_entry(title='First',  category='Fees', is_published=True, display_order=1)
        resp = client.get('/legislation')
        body = resp.data.decode()
        assert body.index('First') < body.index('Second')


# ── Admin access control ──────────────────────────────────────────────────────

class TestLegislationAdminAccess:

    def test_unauthenticated_list_redirects_to_login(self, client):
        """Anonymous GET /admin/legislation must redirect to login (Flask-Login 302).
        The @login_required decorator intercepts before @role_required, so the
        response is a redirect rather than a 401."""
        resp = client.get('/admin/legislation')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_non_superadmin_list_returns_403(self, app, client):
        """Regular user GET /admin/legislation must be rejected with 403."""
        user = _make_user('+910000000901', role='user')
        _login(client, app, user)
        resp = client.get('/admin/legislation')
        assert resp.status_code == 403

    def test_non_superadmin_create_returns_403(self, app, client):
        """Regular user POST /admin/legislation/create must be rejected with 403."""
        user = _make_user('+910000000902', role='user')
        _login(client, app, user)
        resp = _post_create(client)
        assert resp.status_code == 403

    def test_non_superadmin_toggle_returns_403(self, app, client):
        """Regular user POST /toggle must be rejected with 403."""
        user = _make_user('+910000000903', role='user')
        _login(client, app, user)
        entry = _make_entry()
        resp = client.post(f'/admin/legislation/{entry.id}/toggle', data={})
        assert resp.status_code == 403

    def test_non_superadmin_delete_returns_403(self, app, client):
        """Regular user POST /delete must be rejected with 403."""
        user = _make_user('+910000000904', role='user')
        _login(client, app, user)
        entry = _make_entry()
        resp = client.post(f'/admin/legislation/{entry.id}/delete', data={})
        assert resp.status_code == 403


# ── Admin CRUD ────────────────────────────────────────────────────────────────

class TestLegislationAdminCRUD:

    def test_superadmin_can_create(self, app, client):
        """Superadmin POST to /create returns ok=True and writes a DB row."""
        admin = _make_user('+910000000910', role='superadmin')
        _login(client, app, admin)

        before = Legislation.query.count()
        resp = _post_create(client, title='New Law', category='2025 Amendment')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert Legislation.query.count() == before + 1

    def test_create_writes_audit_log(self, app, client):
        """Every successful create must write one LEGISLATION_CREATED AuditLog row."""
        admin = _make_user('+910000000911', role='superadmin')
        _login(client, app, admin)

        before = AuditLog.query.filter_by(action='LEGISLATION_CREATED').count()
        _post_create(client, title='Audit Law')
        after = AuditLog.query.filter_by(action='LEGISLATION_CREATED').count()
        assert after == before + 1

    def test_missing_title_returns_400(self, app, client):
        """POST create without title must return 400 and not create a row."""
        admin = _make_user('+910000000912', role='superadmin')
        _login(client, app, admin)

        before = Legislation.query.count()
        resp = client.post('/admin/legislation/create', data={'category': '2025 Amendment'})
        assert resp.status_code == 400
        assert resp.get_json()['ok'] is False
        assert Legislation.query.count() == before

    def test_missing_category_returns_400(self, app, client):
        """POST create without category must return 400."""
        admin = _make_user('+910000000913', role='superadmin')
        _login(client, app, admin)

        resp = client.post('/admin/legislation/create', data={'title': 'No Category'})
        assert resp.status_code == 400
        assert resp.get_json()['ok'] is False

    def test_csrf_enforced_on_create(self, app, client):
        """POST without csrf_token must return 400 when WTF_CSRF_ENABLED=True.

        conftest disables CSRF globally; this test re-enables it locally
        and restores the original setting in a finally block so other tests
        are unaffected. If Flask-WTF CSRF validation proves flaky in this
        context, the test can be replaced with an assertion that CSRFProtect
        is registered (app.extensions['csrf']).
        """
        admin = _make_user('+910000000914', role='superadmin')
        _login(client, app, admin)

        app.config['WTF_CSRF_ENABLED'] = True
        try:
            resp = client.post('/admin/legislation/create', data={
                'title': 'No CSRF',
                'category': '2025 Amendment',
                # csrf_token intentionally omitted
            })
            assert resp.status_code == 400
        finally:
            app.config['WTF_CSRF_ENABLED'] = False

    def test_superadmin_can_toggle_publish(self, app, client):
        """POST /toggle flips is_published in the DB and returns the new state."""
        admin = _make_user('+910000000915', role='superadmin')
        _login(client, app, admin)

        entry = _make_entry(is_published=False)
        resp = client.post(f'/admin/legislation/{entry.id}/toggle', data={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['is_published'] is True

        db.session.refresh(entry)
        assert entry.is_published is True

    def test_toggle_writes_audit_log(self, app, client):
        """Toggle must write one LEGISLATION_TOGGLED AuditLog row."""
        admin = _make_user('+910000000916', role='superadmin')
        _login(client, app, admin)

        entry = _make_entry(is_published=False)
        before = AuditLog.query.filter_by(action='LEGISLATION_TOGGLED').count()
        client.post(f'/admin/legislation/{entry.id}/toggle', data={})
        after = AuditLog.query.filter_by(action='LEGISLATION_TOGGLED').count()
        assert after == before + 1

    def test_superadmin_can_delete(self, app, client):
        """POST /delete removes the row from the DB."""
        admin = _make_user('+910000000917', role='superadmin')
        _login(client, app, admin)

        entry = _make_entry(title='To Be Deleted')
        entry_id = entry.id
        resp = client.post(f'/admin/legislation/{entry_id}/delete', data={})
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        assert db.session.get(Legislation, entry_id) is None

    def test_delete_writes_audit_log(self, app, client):
        """Delete must write one LEGISLATION_DELETED AuditLog row."""
        admin = _make_user('+910000000918', role='superadmin')
        _login(client, app, admin)

        entry = _make_entry(title='Delete Audit Test')
        before = AuditLog.query.filter_by(action='LEGISLATION_DELETED').count()
        client.post(f'/admin/legislation/{entry.id}/delete', data={})
        after = AuditLog.query.filter_by(action='LEGISLATION_DELETED').count()
        assert after == before + 1

    def test_delete_nonexistent_returns_404(self, app, client):
        """POST /delete on a missing ID must return 404."""
        admin = _make_user('+910000000919', role='superadmin')
        _login(client, app, admin)

        resp = client.post('/admin/legislation/99999/delete', data={})
        assert resp.status_code == 404
        assert resp.get_json()['ok'] is False

    def test_update_entry(self, app, client):
        """POST /update changes the title in the DB and returns ok=True."""
        admin = _make_user('+910000000920', role='superadmin')
        _login(client, app, admin)

        entry = _make_entry(title='Original Title')
        resp = client.post(f'/admin/legislation/{entry.id}/update', data={
            'title':    'Updated Title',
            'category': '2025 Amendment',
        })
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        db.session.refresh(entry)
        assert entry.title == 'Updated Title'

    def test_last_verified_on_parsed_correctly(self, app, client):
        """last_verified_on date string must be stored as a date object."""
        admin = _make_user('+910000000921', role='superadmin')
        _login(client, app, admin)

        import datetime
        resp = _post_create(
            client,
            title='Date Test',
            category='Fees & Royalty',
            last_verified_on='2025-03-15',
        )
        assert resp.status_code == 200
        entry = Legislation.query.filter_by(title='Date Test').first()
        assert entry is not None
        assert entry.last_verified_on == datetime.date(2025, 3, 15)

    def test_empty_last_verified_on_stored_as_none(self, app, client):
        """Empty last_verified_on must be stored as None, not an empty string."""
        admin = _make_user('+910000000922', role='superadmin')
        _login(client, app, admin)

        _post_create(client, title='No Date', last_verified_on='')
        entry = Legislation.query.filter_by(title='No Date').first()
        assert entry is not None
        assert entry.last_verified_on is None

    def test_is_published_checkbox_false_when_absent(self, app, client):
        """When is_published checkbox is absent from form, entry is unpublished."""
        admin = _make_user('+910000000923', role='superadmin')
        _login(client, app, admin)

        _post_create(client, title='Checkbox Absent')
        entry = Legislation.query.filter_by(title='Checkbox Absent').first()
        assert entry is not None
        assert entry.is_published is False

    def test_is_published_true_when_checked(self, app, client):
        """When is_published=1 is in form data, entry is published."""
        admin = _make_user('+910000000924', role='superadmin')
        _login(client, app, admin)

        _post_create(client, title='Checkbox Present', is_published='1')
        entry = Legislation.query.filter_by(title='Checkbox Present').first()
        assert entry is not None
        assert entry.is_published is True
