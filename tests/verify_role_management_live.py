import urllib.request
import json
import time

VITE_URL = 'http://localhost:5173/api/v1'
BACKEND_URL = 'http://127.0.0.1:8000/api/v1'

def api_request(base_url, path, method='GET', data=None):
    url = f"{base_url}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header('Accept', 'application/json')
    if data:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))
    except Exception as e:
        return 0, {'error': str(e)}

def run_tests():
    print("=" * 70)
    print("LIVE VERIFICATION: DELETE CRITERION + ACTIVE ROLE MANAGEMENT")
    print("=" * 70)

    # 0. Health check
    st, health = api_request(VITE_URL, '/health')
    print(f"Health through Vite proxy: {st}, DB connected: {health.get('database_connected')}")
    assert st == 200 and health.get('database_connected') is True

    # TEST 1: DELETE CRITERION FLOW
    print("\n--- TEST 1: DELETE CRITERION FLOW ---")
    st, roles = api_request(VITE_URL, '/roles')
    role1 = roles[0]
    role1_id = role1['id']
    print(f"Active Role: {role1['title']} ({role1_id})")
    print(f"Initial criteria: {[r['name'] for r in role1['requirements']]}")

    # Add a temporary criterion to delete
    st, add_res = api_request(VITE_URL, f"/roles/{role1_id}/requirements", method='POST', data={
        "name": "Cloud Networking VPC",
        "category": "NICE_TO_HAVE",
        "description": "Subnet and routing table configurations.",
        "weight": 1.0
    })
    assert st == 201
    crit_id = add_res['id']
    print(f"Added criterion: '{add_res['name']}' (ID: {crit_id})")

    # Delete the criterion via DELETE API
    st, del_res = api_request(VITE_URL, f"/roles/{role1_id}/requirements/{crit_id}", method='DELETE')
    print(f"DELETE response: status={st}, body={del_res}")
    assert st == 200
    assert del_res.get('success') is True
    assert del_res.get('deleted_id') == crit_id
    assert "deleted successfully" in del_res.get('message', '').lower()

    # Verify persistence: refresh role from backend
    st, role1_refreshed = api_request(BACKEND_URL, f"/roles/{role1_id}")
    refreshed_names = [r['name'] for r in role1_refreshed['requirements']]
    print(f"Refreshed criteria after deletion: {refreshed_names}")
    assert "Cloud Networking VPC" not in refreshed_names
    print("[PASS] Test 1: Delete succeeded with clean JSON and persists across re-fetch.")

    # TEST 2: ADD ROLE
    print("\n--- TEST 2: ADD ACTIVE ROLE ---")
    new_role_payload = {
        "title": "Machine Learning Engineer",
        "department": "Artificial Intelligence",
        "min_years_experience": 2,
        "raw_jd_text": "Train, evaluate, and optimize deep learning transformer models in PyTorch."
    }
    st, create_res = api_request(VITE_URL, "/roles", method='POST', data=new_role_payload)
    print(f"POST /roles response: status={st}, body={create_res}")
    assert st == 201
    ml_role_id = create_res['id']
    assert create_res['title'] == "Machine Learning Engineer"
    assert create_res['department'] == "Artificial Intelligence"
    assert create_res['min_years_experience'] == 2

    # Verify database persistence
    st, db_role = api_request(BACKEND_URL, f"/roles/{ml_role_id}")
    assert st == 200
    assert db_role['title'] == "Machine Learning Engineer"
    print(f"[PASS] Test 2: Role created and persisted in DB with ID {ml_role_id}.")

    # TEST 3: ROLE ISOLATION
    print("\n--- TEST 3: ROLE ISOLATION (INITIAL CRITERIA) ---")
    print(f"New role initial requirements: {db_role.get('requirements', [])}")
    assert len(db_role.get('requirements', [])) == 0, "New role should start without unrequested criteria"
    
    # Check comparison matrix for new role
    st, ml_matrix = api_request(VITE_URL, f"/roles/{ml_role_id}/matrix")
    assert st == 200
    print(f"New role matrix requirements: {ml_matrix.get('requirements', [])}")
    assert len(ml_matrix.get('requirements', [])) == 0
    print("[PASS] Test 3: New role is isolated with zero criteria leakage from previous role.")

    # TEST 4: ADD CRITERION TO NEW ROLE
    print("\n--- TEST 4: ADD CRITERION TO NEW ROLE ---")
    st, crit_ml = api_request(VITE_URL, f"/roles/{ml_role_id}/requirements", method='POST', data={
        "name": "Machine Learning",
        "category": "MUST_HAVE",
        "description": "Classical and deep learning model training and inference.",
        "weight": 1.0
    })
    assert st == 201
    ml_crit_id = crit_ml['id']
    print(f"Added criterion '{crit_ml['name']}' to Role '{create_res['title']}'")

    # Verify criterion belongs ONLY to Role B
    st, role1_check = api_request(VITE_URL, f"/roles/{role1_id}")
    role1_names = [r['name'] for r in role1_check['requirements']]
    assert "Machine Learning" not in role1_names, "Machine Learning must not leak into Role 1"

    st, ml_role_check = api_request(VITE_URL, f"/roles/{ml_role_id}")
    ml_role_names = [r['name'] for r in ml_role_check['requirements']]
    assert "Machine Learning" in ml_role_names
    print(f"[PASS] Test 4: 'Machine Learning' belongs strictly to 'Machine Learning Engineer'.")

    # TEST 5: DUPLICATE PREVENTION FOR NEW ROLE
    print("\n--- TEST 5: DUPLICATE PREVENTION ---")
    st, dup_res = api_request(VITE_URL, f"/roles/{ml_role_id}/requirements", method='POST', data={
        "name": "machine learning",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    print(f"Duplicate attempt response: status={st}, detail={dup_res.get('detail')}")
    assert st == 400
    assert dup_res.get('detail') == "This criterion already exists for the selected role."
    print("[PASS] Test 5: Normalized duplicate 'machine learning' was rejected.")

    # TEST 6: DELETE FROM NEW ROLE
    print("\n--- TEST 6: DELETE CRITERION FROM NEW ROLE ---")
    # Add a second criterion so we don't hit the "cannot delete only remaining criterion" invariant
    st, crit_py = api_request(VITE_URL, f"/roles/{ml_role_id}/requirements", method='POST', data={
        "name": "Python & NumPy",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    assert st == 201

    # Now delete "Machine Learning"
    st, del_ml_res = api_request(VITE_URL, f"/roles/{ml_role_id}/requirements/{ml_crit_id}", method='DELETE')
    print(f"Delete response: status={st}, body={del_ml_res}")
    assert st == 200
    assert del_ml_res.get('success') is True
    assert del_ml_res.get('deleted_id') == ml_crit_id

    # Verify matrix no longer contains "Machine Learning"
    st, ml_matrix_after = api_request(VITE_URL, f"/roles/{ml_role_id}/matrix")
    matrix_after_reqs = [r['name'] for r in ml_matrix_after['requirements']]
    print(f"Matrix columns after deleting 'Machine Learning': {matrix_after_reqs}")
    assert "Machine Learning" not in matrix_after_reqs
    assert "Python & NumPy" in matrix_after_reqs
    print("[PASS] Test 6: Deletion succeeded, database and matrix accurately updated.")

    print("\n" + "=" * 70)
    print(">>> ALL 6 END-TO-END ACCEPTANCE TESTS PASSED PERFECTLY! <<<")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
