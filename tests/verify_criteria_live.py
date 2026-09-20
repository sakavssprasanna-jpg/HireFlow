import urllib.request
import json

BASE_URL = 'http://127.0.0.1:8000/api/v1'

def api_call(path, method='GET', data=None):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))

def main():
    print("=== 1. Health check ===")
    status, health = api_call('/health')
    print(f"Health status: {status}, DB connected: {health.get('database_connected')}")
    assert status == 200 and health['database_connected'] is True

    print("\n=== 2. List Roles ===")
    status, roles = api_call('/roles')
    print(f"Total roles: {len(roles)}")
    for r in roles:
        print(f"Role: {r['title']} (ID: {r['id']}, {len(r['requirements'])} criteria)")
    assert len(roles) >= 2

    role1 = roles[0]
    role1_id = role1['id']
    print("\nRole 1 criteria before Test A:", [req['name'] for req in role1['requirements']])

    print("\n=== Scenario A: Add Criterion ===")
    status, add_resp = api_call(f"/roles/{role1_id}/requirements", method='POST', data={
        "name": "Golang Microservices",
        "category": "MUST_HAVE",
        "description": "Production microservice development in Go.",
        "weight": 1.0
    })
    print(f"Add status: {status}, Created: {add_resp['name']}, ID: {add_resp['id']}")
    assert status == 201

    # Verify matrix includes Golang Microservices column
    status, matrix = api_call(f"/roles/{role1_id}/matrix")
    matrix_req_names = [r['name'] for r in matrix['requirements']]
    print(f"Matrix requirements columns after Add: {matrix_req_names}")
    assert "Golang Microservices" in matrix_req_names

    print("\n=== Scenario B: Duplicate Prevention ===")
    # Exact duplicate
    status, dup1 = api_call(f"/roles/{role1_id}/requirements", method='POST', data={
        "name": "Golang Microservices",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    print(f"Exact duplicate: status={status}, detail={dup1.get('detail')}")
    assert status == 400 and dup1['detail'] == "This criterion already exists for the selected role."

    # Lowercase duplicate
    status, dup2 = api_call(f"/roles/{role1_id}/requirements", method='POST', data={
        "name": "golang microservices",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    print(f"Lowercase duplicate: status={status}, detail={dup2.get('detail')}")
    assert status == 400 and dup2['detail'] == "This criterion already exists for the selected role."

    # UPPERCASE duplicate
    status, dup3 = api_call(f"/roles/{role1_id}/requirements", method='POST', data={
        "name": "GOLANG MICROSERVICES",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    print(f"Uppercase duplicate: status={status}, detail={dup3.get('detail')}")
    assert status == 400 and dup3['detail'] == "This criterion already exists for the selected role."

    # Whitespace variants duplicate
    status, dup4 = api_call(f"/roles/{role1_id}/requirements", method='POST', data={
        "name": "   golang    microservices   ",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    print(f"Whitespace variant duplicate: status={status}, detail={dup4.get('detail')}")
    assert status == 400 and dup4['detail'] == "This criterion already exists for the selected role."

    print("\n=== Scenario C & D: Delete Criterion & Screening Propagation ===")
    req_id_to_delete = add_resp['id']
    status, del_resp = api_call(f"/roles/{role1_id}/requirements/{req_id_to_delete}", method='DELETE')
    print(f"Delete status: {status}, response={del_resp}")
    assert status == 200

    # Verify matrix columns no longer include Golang Microservices
    status, matrix_after = api_call(f"/roles/{role1_id}/matrix")
    matrix_after_req_names = [r['name'] for r in matrix_after['requirements']]
    print(f"Matrix requirements columns after Delete: {matrix_after_req_names}")
    assert "Golang Microservices" not in matrix_after_req_names

    # Verify role requirements no longer include Golang Microservices
    status, role1_refreshed = api_call(f"/roles/{role1_id}")
    refreshed_req_names = [r['name'] for r in role1_refreshed['requirements']]
    print(f"Role 1 requirements after Delete: {refreshed_req_names}")
    assert "Golang Microservices" not in refreshed_req_names

    print("\n=== Scenario E: Dynamic Role Switch Verification ===")
    role2 = roles[1]
    role2_id = role2['id']
    status, matrix2 = api_call(f"/roles/{role2_id}/matrix")
    print(f"Role 2 Title: {matrix2['role_title']}")
    print(f"Role 2 Matrix columns: {[r['name'] for r in matrix2['requirements']]}")
    assert matrix2['role_title'] == role2['title']
    assert len(matrix2['requirements']) == len(role2['requirements'])

    print("\n>>> ALL 5 LIVE SCENARIOS VERIFIED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    main()
