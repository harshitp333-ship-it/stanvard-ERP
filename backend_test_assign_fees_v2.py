#!/usr/bin/env python3
"""
Backend Testing Script for Assign Fees Redesign v2 (Jul 2026)

Tests the SIX new backend behaviours (A through F) as requested:
A) POST /api/fees/assignments with full new payload, live notify
B) POST with is_draft=true (no notification)
C) POST with notify_parent=false (no notification)
D) PATCH with notify_parent=true (notification created, field not persisted)
E) GET /api/fees/assignments/previous-for-student/{id}
F) Regression tests
"""

import requests
import os
from typing import Dict, Any, Optional

# Backend base URL
BACKEND_URL = "https://code-standard-1.preview.emergentagent.com/api"

# Test credentials
SUPER_ADMIN_EMAIL = "superadmin@stanvard.school"
SUPER_ADMIN_PASSWORD = "Stanvard@2026"
SCHOOL_ID = "034cab3a-3107-4cf2-bfdb-3bba434a5367"  # KNP

# Existing student to use (Divyansh Dangi, active)
STUDENT_ID = "e30e6481-848e-4b3b-a45e-0385ff02bc69"

# Test results tracking
test_results = {
    'A': {'passed': 0, 'failed': 0, 'tests': []},
    'B': {'passed': 0, 'failed': 0, 'tests': []},
    'C': {'passed': 0, 'failed': 0, 'tests': []},
    'D': {'passed': 0, 'failed': 0, 'tests': []},
    'E': {'passed': 0, 'failed': 0, 'tests': []},
    'F': {'passed': 0, 'failed': 0, 'tests': []},
}

def log_test(section: str, test_name: str, passed: bool, details: str = ""):
    """Log a test result"""
    result = "✓ PASS" if passed else "✗ FAIL"
    print(f"  [{section}] {result}: {test_name}")
    if details:
        print(f"      {details}")
    
    test_results[section]['tests'].append({
        'name': test_name,
        'passed': passed,
        'details': details
    })
    if passed:
        test_results[section]['passed'] += 1
    else:
        test_results[section]['failed'] += 1

def login(email: str, password: str) -> Optional[str]:
    """Login and return access token"""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": email, "password": password},
            headers={"X-School-Id": SCHOOL_ID}
        )
        if resp.status_code == 200:
            return resp.json().get('access_token')
        else:
            print(f"Login failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def get_headers(token: str) -> Dict[str, str]:
    """Get request headers with auth token"""
    return {
        "Authorization": f"Bearer {token}",
        "X-School-Id": SCHOOL_ID,
        "Content-Type": "application/json"
    }

def get_active_fee_plan(token: str) -> Optional[str]:
    """Get the first active fee plan ID"""
    try:
        resp = requests.get(
            f"{BACKEND_URL}/fees/plans",
            headers=get_headers(token)
        )
        if resp.status_code == 200:
            plans = resp.json()
            if plans and len(plans) > 0:
                return plans[0]['id']
        return None
    except Exception as e:
        print(f"Error getting fee plans: {e}")
        return None

def count_notifications_for_student(token: str, student_id: str, kind: str = 'fee_reminder') -> int:
    """Count notifications for a specific student"""
    try:
        resp = requests.get(
            f"{BACKEND_URL}/notifications",
            headers=get_headers(token)
        )
        if resp.status_code == 200:
            notifications = resp.json()
            count = 0
            for n in notifications:
                if n.get('kind') == kind and student_id in (n.get('student_ids') or []):
                    count += 1
            return count
        return 0
    except Exception as e:
        print(f"Error counting notifications: {e}")
        return 0

def test_section_a(token: str, fee_plan_id: str):
    """
    A) POST /api/fees/assignments — full new payload, live notify.
    Expected:
      - HTTP 200; response echoes collection_months, installments (len 4),
        due_day_of_month=15, is_draft=false.
      - Then GET /api/notifications and confirm a fresh notification exists
        with kind='fee_reminder', student_ids contains the STU id, and title
        starts with "New fee assigned".
      - Store the returned assignment id → ASSIGN_A_ID for later steps.
    """
    print("\n=== SECTION A: POST /api/fees/assignments with full payload + notify_parent=true ===")
    
    # Get initial notification count
    initial_notif_count = count_notifications_for_student(token, STUDENT_ID)
    print(f"Initial notification count for student: {initial_notif_count}")
    
    # Create assignment with full payload
    payload = {
        "student_id": STUDENT_ID,
        "fee_plan_id": fee_plan_id,
        "academic_session": "2026-27",
        "discount_percent": 10,
        "discount_reason": "Sibling Discount",
        "collection_months": [4, 5, 7, 8, 9, 10, 11, 12, 1, 2],
        "installments": [
            {"month": 4, "year": 2026, "amount": 2520, "due_date": "2026-04-15", "last_payment_date": "2026-04-30", "status": "active"},
            {"month": 5, "year": 2026, "amount": 2520, "due_date": "2026-05-15", "last_payment_date": "2026-05-31", "status": "active"},
            {"month": 6, "year": 2026, "amount": 0, "label": "Summer Vacation", "status": "skip"},
            {"month": 3, "year": 2027, "amount": 0, "label": "Session End", "status": "skip"}
        ],
        "due_day_of_month": 15,
        "notify_parent": True,
        "is_draft": False
    }
    
    try:
        resp = requests.post(
            f"{BACKEND_URL}/fees/assignments",
            json=payload,
            headers=get_headers(token)
        )
        
        # Test A.1: HTTP 200
        log_test('A', 'POST returns HTTP 200', resp.status_code == 200, 
                 f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"Response: {resp.text}")
            return None
        
        data = resp.json()
        assign_a_id = data.get('id')
        
        # Test A.2: Response echoes collection_months
        log_test('A', 'Response echoes collection_months', 
                 data.get('collection_months') == payload['collection_months'],
                 f"Expected: {payload['collection_months']}, Got: {data.get('collection_months')}")
        
        # Test A.3: Response has installments with length 4
        installments = data.get('installments', [])
        log_test('A', 'Response has 4 installments', 
                 len(installments) == 4,
                 f"Expected: 4, Got: {len(installments)}")
        
        # Test A.4: due_day_of_month = 15
        log_test('A', 'due_day_of_month = 15', 
                 data.get('due_day_of_month') == 15,
                 f"Expected: 15, Got: {data.get('due_day_of_month')}")
        
        # Test A.5: is_draft = false
        log_test('A', 'is_draft = false', 
                 data.get('is_draft') == False,
                 f"Expected: False, Got: {data.get('is_draft')}")
        
        # Test A.6: Notification created
        import time
        time.sleep(1)  # Give notification time to be created
        new_notif_count = count_notifications_for_student(token, STUDENT_ID)
        log_test('A', 'Notification count increased', 
                 new_notif_count > initial_notif_count,
                 f"Initial: {initial_notif_count}, New: {new_notif_count}")
        
        # Test A.7: Verify notification details
        resp_notif = requests.get(f"{BACKEND_URL}/notifications", headers=get_headers(token))
        if resp_notif.status_code == 200:
            notifications = resp_notif.json()
            fee_notif = None
            for n in notifications:
                if n.get('kind') == 'fee_reminder' and STUDENT_ID in (n.get('student_ids') or []):
                    fee_notif = n
                    break
            
            if fee_notif:
                title_starts_correct = fee_notif.get('title', '').startswith('New fee assigned')
                log_test('A', 'Notification title starts with "New fee assigned"', 
                         title_starts_correct,
                         f"Title: {fee_notif.get('title')}")
            else:
                log_test('A', 'Found fee_reminder notification', False, 
                         "No fee_reminder notification found")
        
        return assign_a_id
        
    except Exception as e:
        log_test('A', 'POST request execution', False, f"Error: {e}")
        return None

def test_section_b(token: str, fee_plan_id: str, assign_a_id: Optional[str]):
    """
    B) DELETE ASSIGN_A_ID, then POST the same payload but with "is_draft": true.
    Expected: HTTP 200; the count of notifications for this student remains
    the same (no new fee_reminder was created).
    Cleanup: DELETE this new assignment id.
    """
    print("\n=== SECTION B: POST with is_draft=true (no notification) ===")
    
    # Delete ASSIGN_A_ID first
    if assign_a_id:
        try:
            resp = requests.delete(
                f"{BACKEND_URL}/fees/assignments/{assign_a_id}",
                headers=get_headers(token)
            )
            log_test('B', 'DELETE ASSIGN_A_ID', resp.status_code == 200,
                     f"Status: {resp.status_code}")
        except Exception as e:
            log_test('B', 'DELETE ASSIGN_A_ID', False, f"Error: {e}")
    
    # Get notification count before
    notif_count_before = count_notifications_for_student(token, STUDENT_ID)
    
    # Create assignment with is_draft=true
    payload = {
        "student_id": STUDENT_ID,
        "fee_plan_id": fee_plan_id,
        "academic_session": "2026-27",
        "discount_percent": 10,
        "discount_reason": "Sibling Discount",
        "collection_months": [4, 5, 7, 8, 9, 10, 11, 12, 1, 2],
        "installments": [
            {"month": 4, "year": 2026, "amount": 2520, "due_date": "2026-04-15", "last_payment_date": "2026-04-30", "status": "active"},
            {"month": 5, "year": 2026, "amount": 2520, "due_date": "2026-05-15", "last_payment_date": "2026-05-31", "status": "active"},
            {"month": 6, "year": 2026, "amount": 0, "label": "Summer Vacation", "status": "skip"},
            {"month": 3, "year": 2027, "amount": 0, "label": "Session End", "status": "skip"}
        ],
        "due_day_of_month": 15,
        "notify_parent": True,
        "is_draft": True  # DRAFT MODE
    }
    
    try:
        resp = requests.post(
            f"{BACKEND_URL}/fees/assignments",
            json=payload,
            headers=get_headers(token)
        )
        
        log_test('B', 'POST returns HTTP 200', resp.status_code == 200,
                 f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"Response: {resp.text}")
            return None
        
        data = resp.json()
        assign_b_id = data.get('id')
        
        # Test B.2: Notification count unchanged
        import time
        time.sleep(1)
        notif_count_after = count_notifications_for_student(token, STUDENT_ID)
        log_test('B', 'Notification count unchanged (draft suppresses notification)', 
                 notif_count_after == notif_count_before,
                 f"Before: {notif_count_before}, After: {notif_count_after}")
        
        # Cleanup: DELETE this assignment
        if assign_b_id:
            resp_del = requests.delete(
                f"{BACKEND_URL}/fees/assignments/{assign_b_id}",
                headers=get_headers(token)
            )
            log_test('B', 'Cleanup: DELETE assignment', resp_del.status_code == 200,
                     f"Status: {resp_del.status_code}")
        
        return assign_b_id
        
    except Exception as e:
        log_test('B', 'POST request execution', False, f"Error: {e}")
        return None

def test_section_c(token: str, fee_plan_id: str):
    """
    C) POST the same payload but with "notify_parent": false and is_draft false.
    Expected: HTTP 200; no new fee_reminder notification created.
    Cleanup: DELETE this assignment id.
    """
    print("\n=== SECTION C: POST with notify_parent=false (no notification) ===")
    
    notif_count_before = count_notifications_for_student(token, STUDENT_ID)
    
    payload = {
        "student_id": STUDENT_ID,
        "fee_plan_id": fee_plan_id,
        "academic_session": "2026-27",
        "discount_percent": 10,
        "discount_reason": "Sibling Discount",
        "collection_months": [4, 5, 7, 8, 9, 10, 11, 12, 1, 2],
        "installments": [
            {"month": 4, "year": 2026, "amount": 2520, "due_date": "2026-04-15", "last_payment_date": "2026-04-30", "status": "active"},
            {"month": 5, "year": 2026, "amount": 2520, "due_date": "2026-05-15", "last_payment_date": "2026-05-31", "status": "active"},
            {"month": 6, "year": 2026, "amount": 0, "label": "Summer Vacation", "status": "skip"},
            {"month": 3, "year": 2027, "amount": 0, "label": "Session End", "status": "skip"}
        ],
        "due_day_of_month": 15,
        "notify_parent": False,  # NO NOTIFICATION
        "is_draft": False
    }
    
    try:
        resp = requests.post(
            f"{BACKEND_URL}/fees/assignments",
            json=payload,
            headers=get_headers(token)
        )
        
        log_test('C', 'POST returns HTTP 200', resp.status_code == 200,
                 f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"Response: {resp.text}")
            return None
        
        data = resp.json()
        assign_c_id = data.get('id')
        
        # Test C.2: Notification count unchanged
        import time
        time.sleep(1)
        notif_count_after = count_notifications_for_student(token, STUDENT_ID)
        log_test('C', 'Notification count unchanged (notify_parent=false)', 
                 notif_count_after == notif_count_before,
                 f"Before: {notif_count_before}, After: {notif_count_after}")
        
        # Cleanup: DELETE this assignment
        if assign_c_id:
            resp_del = requests.delete(
                f"{BACKEND_URL}/fees/assignments/{assign_c_id}",
                headers=get_headers(token)
            )
            log_test('C', 'Cleanup: DELETE assignment', resp_del.status_code == 200,
                     f"Status: {resp_del.status_code}")
        
        return assign_c_id
        
    except Exception as e:
        log_test('C', 'POST request execution', False, f"Error: {e}")
        return None

def test_section_d(token: str, fee_plan_id: str):
    """
    D) POST a fresh assignment (notify_parent=false, is_draft=false) → ASSIGN_D_ID.
    Then PATCH /api/fees/assignments/ASSIGN_D_ID with
        { "remarks": "updated", "notify_parent": true }
    Expected:
      - HTTP 200.
      - GET /api/fees/assignments/ASSIGN_D_ID → the doc has NO field named
        'notify_parent' (transient — must not be persisted).
      - The doc's remarks is now "updated".
      - A new fee_reminder notification appeared with title starting
        "New fee assigned".
    Cleanup: DELETE ASSIGN_D_ID.
    """
    print("\n=== SECTION D: PATCH with notify_parent=true (notification created, field not persisted) ===")
    
    # Create assignment without notification
    payload = {
        "student_id": STUDENT_ID,
        "fee_plan_id": fee_plan_id,
        "academic_session": "2026-27",
        "discount_percent": 5,
        "discount_reason": "Merit",
        "collection_months": [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3],
        "due_day_of_month": 15,
        "notify_parent": False,
        "is_draft": False
    }
    
    try:
        resp = requests.post(
            f"{BACKEND_URL}/fees/assignments",
            json=payload,
            headers=get_headers(token)
        )
        
        log_test('D', 'POST initial assignment', resp.status_code == 200,
                 f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"Response: {resp.text}")
            return None
        
        data = resp.json()
        assign_d_id = data.get('id')
        
        # Get notification count before PATCH
        notif_count_before = count_notifications_for_student(token, STUDENT_ID)
        
        # PATCH with notify_parent=true
        patch_payload = {
            "remarks": "updated",
            "notify_parent": True
        }
        
        resp_patch = requests.patch(
            f"{BACKEND_URL}/fees/assignments/{assign_d_id}",
            json=patch_payload,
            headers=get_headers(token)
        )
        
        log_test('D', 'PATCH returns HTTP 200', resp_patch.status_code == 200,
                 f"Status: {resp_patch.status_code}")
        
        if resp_patch.status_code != 200:
            print(f"Response: {resp_patch.text}")
            return None
        
        # GET the assignment to verify (use list endpoint with student_id filter)
        resp_get = requests.get(
            f"{BACKEND_URL}/fees/assignments?student_id={STUDENT_ID}",
            headers=get_headers(token)
        )
        
        if resp_get.status_code == 200:
            assignments = resp_get.json()
            # Find our assignment by ID
            doc = None
            for a in assignments:
                if a.get('id') == assign_d_id:
                    doc = a
                    break
            
            if doc:
                # Test D.3: notify_parent NOT persisted
                has_notify_parent = 'notify_parent' in doc
                log_test('D', 'notify_parent NOT persisted (transient field)', 
                         not has_notify_parent,
                         f"Field present: {has_notify_parent}")
                
                # Test D.4: remarks updated
                log_test('D', 'remarks updated to "updated"', 
                         doc.get('remarks') == 'updated',
                         f"Expected: 'updated', Got: {doc.get('remarks')}")
            else:
                log_test('D', 'GET assignment by ID', False, 
                         f"Assignment {assign_d_id} not found in list")
        
        # Test D.5: Notification created
        import time
        time.sleep(1)
        notif_count_after = count_notifications_for_student(token, STUDENT_ID)
        log_test('D', 'Notification count increased after PATCH', 
                 notif_count_after > notif_count_before,
                 f"Before: {notif_count_before}, After: {notif_count_after}")
        
        # Test D.6: Verify notification title
        resp_notif = requests.get(f"{BACKEND_URL}/notifications", headers=get_headers(token))
        if resp_notif.status_code == 200:
            notifications = resp_notif.json()
            # Get the most recent fee_reminder for this student
            recent_notif = None
            for n in reversed(notifications):
                if n.get('kind') == 'fee_reminder' and STUDENT_ID in (n.get('student_ids') or []):
                    recent_notif = n
                    break
            
            if recent_notif:
                title_starts_correct = recent_notif.get('title', '').startswith('New fee assigned')
                log_test('D', 'Notification title starts with "New fee assigned"', 
                         title_starts_correct,
                         f"Title: {recent_notif.get('title')}")
        
        # Cleanup: DELETE this assignment
        if assign_d_id:
            resp_del = requests.delete(
                f"{BACKEND_URL}/fees/assignments/{assign_d_id}",
                headers=get_headers(token)
            )
            log_test('D', 'Cleanup: DELETE assignment', resp_del.status_code == 200,
                     f"Status: {resp_del.status_code}")
        
        return assign_d_id
        
    except Exception as e:
        log_test('D', 'Test execution', False, f"Error: {e}")
        return None

def test_section_e(token: str, fee_plan_id: str):
    """
    E) Previous-for-student flow.
    E1) Pick a student with no assignments (or use a fresh student). Call
        GET /api/fees/assignments/previous-for-student/<STU_NEW>
        Expect { "previous": null }.
    E2) For an existing student that already has a current-session assignment,
        call the same endpoint. Since no prior session assignment exists,
        expect { "previous": null }.
    E3) Create two assignments for the same student:
        - first with academic_session="2025-26" (POST)
        - second with academic_session="2026-27" (POST)
        Then GET previous-for-student — expect previous != null and
        previous.academic_session == "2025-26" and source_session == "2025-26".
    Cleanup: DELETE both.
    """
    print("\n=== SECTION E: GET /api/fees/assignments/previous-for-student/{id} ===")
    
    # E1: Test with student that has no assignments (use a different student)
    # First, get a list of students and find one without assignments
    try:
        resp_students = requests.get(
            f"{BACKEND_URL}/students?limit=100",
            headers=get_headers(token)
        )
        
        if resp_students.status_code == 200:
            students = resp_students.json()
            # Try to find a student without assignments
            test_student_id = None
            for student in students:
                sid = student.get('id')
                if sid and sid != STUDENT_ID:
                    # Check if this student has assignments
                    resp_check = requests.get(
                        f"{BACKEND_URL}/fees/assignments?student_id={sid}",
                        headers=get_headers(token)
                    )
                    if resp_check.status_code == 200:
                        assignments = resp_check.json()
                        if not assignments or len(assignments) == 0:
                            test_student_id = sid
                            break
            
            if test_student_id:
                # E1: Test with student with no assignments
                resp_prev = requests.get(
                    f"{BACKEND_URL}/fees/assignments/previous-for-student/{test_student_id}",
                    headers=get_headers(token)
                )
                
                log_test('E', 'E1: GET previous-for-student (no assignments)', 
                         resp_prev.status_code == 200,
                         f"Status: {resp_prev.status_code}")
                
                if resp_prev.status_code == 200:
                    data = resp_prev.json()
                    log_test('E', 'E1: Returns {previous: null}', 
                             data.get('previous') is None,
                             f"Response: {data}")
            else:
                log_test('E', 'E1: Find student without assignments', False,
                         "Could not find student without assignments")
        
        # E2: Test with existing student (STUDENT_ID) that has current-session assignment
        resp_prev = requests.get(
            f"{BACKEND_URL}/fees/assignments/previous-for-student/{STUDENT_ID}",
            headers=get_headers(token)
        )
        
        log_test('E', 'E2: GET previous-for-student (current session only)', 
                 resp_prev.status_code == 200,
                 f"Status: {resp_prev.status_code}")
        
        if resp_prev.status_code == 200:
            data = resp_prev.json()
            # Should return null if no prior session exists
            # (Note: This might return a previous assignment if one exists from earlier tests)
            print(f"  E2 Response: {data}")
        
        # E3: Create two assignments with different sessions
        # First: 2025-26
        payload_2025 = {
            "student_id": STUDENT_ID,
            "fee_plan_id": fee_plan_id,
            "academic_session": "2025-26",
            "discount_percent": 5,
            "collection_months": [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3],
            "due_day_of_month": 15,
            "notify_parent": False,
            "is_draft": False
        }
        
        resp_2025 = requests.post(
            f"{BACKEND_URL}/fees/assignments",
            json=payload_2025,
            headers=get_headers(token)
        )
        
        log_test('E', 'E3: POST assignment for 2025-26', 
                 resp_2025.status_code == 200,
                 f"Status: {resp_2025.status_code}")
        
        assign_2025_id = None
        if resp_2025.status_code == 200:
            assign_2025_id = resp_2025.json().get('id')
        
        # Second: 2026-27
        payload_2026 = {
            "student_id": STUDENT_ID,
            "fee_plan_id": fee_plan_id,
            "academic_session": "2026-27",
            "discount_percent": 10,
            "collection_months": [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3],
            "due_day_of_month": 15,
            "notify_parent": False,
            "is_draft": False
        }
        
        resp_2026 = requests.post(
            f"{BACKEND_URL}/fees/assignments",
            json=payload_2026,
            headers=get_headers(token)
        )
        
        log_test('E', 'E3: POST assignment for 2026-27', 
                 resp_2026.status_code == 200,
                 f"Status: {resp_2026.status_code}")
        
        assign_2026_id = None
        if resp_2026.status_code == 200:
            assign_2026_id = resp_2026.json().get('id')
        
        # Now GET previous-for-student
        import time
        time.sleep(1)
        resp_prev = requests.get(
            f"{BACKEND_URL}/fees/assignments/previous-for-student/{STUDENT_ID}",
            headers=get_headers(token)
        )
        
        log_test('E', 'E3: GET previous-for-student (two sessions)', 
                 resp_prev.status_code == 200,
                 f"Status: {resp_prev.status_code}")
        
        if resp_prev.status_code == 200:
            data = resp_prev.json()
            previous = data.get('previous')
            source_session = data.get('source_session')
            
            log_test('E', 'E3: previous is not null', 
                     previous is not None,
                     f"previous: {previous is not None}")
            
            if previous:
                log_test('E', 'E3: previous.academic_session == "2025-26"', 
                         previous.get('academic_session') == '2025-26',
                         f"Expected: '2025-26', Got: {previous.get('academic_session')}")
                
                log_test('E', 'E3: source_session == "2025-26"', 
                         source_session == '2025-26',
                         f"Expected: '2025-26', Got: {source_session}")
        
        # Cleanup: DELETE both assignments
        if assign_2025_id:
            resp_del = requests.delete(
                f"{BACKEND_URL}/fees/assignments/{assign_2025_id}",
                headers=get_headers(token)
            )
            log_test('E', 'E3: Cleanup DELETE 2025-26 assignment', 
                     resp_del.status_code == 200,
                     f"Status: {resp_del.status_code}")
        
        if assign_2026_id:
            resp_del = requests.delete(
                f"{BACKEND_URL}/fees/assignments/{assign_2026_id}",
                headers=get_headers(token)
            )
            log_test('E', 'E3: Cleanup DELETE 2026-27 assignment', 
                     resp_del.status_code == 200,
                     f"Status: {resp_del.status_code}")
        
    except Exception as e:
        log_test('E', 'Test execution', False, f"Error: {e}")

def test_section_f(token: str, fee_plan_id: str):
    """
    F) Regression.
    F1) GET /api/reports/fee-status still returns 375 rows (or similar count
        — the number should not be lower than the prior count, since we
        have not deleted students).
    F2) POST /api/fees/assignments with the MINIMAL legacy payload:
        { "student_id": <STU_UNASSIGNED>, "fee_plan_id": <PLAN>,
          "discount_percent": 5, "discount_reason": "Merit",
          "internal_notes": "test" }
        (no collection_months, no installments, is_draft omitted, notify_parent omitted)
        Expect HTTP 200 and defaults kick in:
        - collection_months == [4,5,6,7,8,9,10,11,12,1,2,3]
        - installments == [] (empty)
        - due_day_of_month == 15
        - is_draft == false
        - internal_notes == "test"
        Cleanup: DELETE.
    """
    print("\n=== SECTION F: Regression Tests ===")
    
    # F1: GET /api/reports/fee-status
    try:
        resp = requests.get(
            f"{BACKEND_URL}/reports/fee-status",
            headers=get_headers(token)
        )
        
        log_test('F', 'F1: GET /api/reports/fee-status returns 200', 
                 resp.status_code == 200,
                 f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get('rows', [])
            row_count = len(rows)
            
            # Should be 375 or similar (not lower)
            log_test('F', 'F1: Row count >= 375 (no students deleted)', 
                     row_count >= 375,
                     f"Row count: {row_count}")
        
        # F2: POST with minimal legacy payload
        # First, find a student without an assignment for 2026-27
        resp_students = requests.get(
            f"{BACKEND_URL}/students?limit=100",
            headers=get_headers(token)
        )
        
        test_student_id = STUDENT_ID  # Default to our test student
        
        if resp_students.status_code == 200:
            students = resp_students.json()
            for student in students:
                sid = student.get('id')
                if sid:
                    # Check if this student has a 2026-27 assignment
                    resp_check = requests.get(
                        f"{BACKEND_URL}/fees/assignments?student_id={sid}",
                        headers=get_headers(token)
                    )
                    if resp_check.status_code == 200:
                        assignments = resp_check.json()
                        has_2026_27 = any(a.get('academic_session') == '2026-27' for a in assignments)
                        if not has_2026_27:
                            test_student_id = sid
                            break
        
        # Minimal payload (legacy format)
        minimal_payload = {
            "student_id": test_student_id,
            "fee_plan_id": fee_plan_id,
            "discount_percent": 5,
            "discount_reason": "Merit",
            "internal_notes": "test"
        }
        
        resp_minimal = requests.post(
            f"{BACKEND_URL}/fees/assignments",
            json=minimal_payload,
            headers=get_headers(token)
        )
        
        log_test('F', 'F2: POST with minimal payload returns 200', 
                 resp_minimal.status_code == 200,
                 f"Status: {resp_minimal.status_code}")
        
        assign_f_id = None
        if resp_minimal.status_code == 200:
            data = resp_minimal.json()
            assign_f_id = data.get('id')
            
            # Test defaults
            log_test('F', 'F2: collection_months defaults to [4,5,6,7,8,9,10,11,12,1,2,3]', 
                     data.get('collection_months') == [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3],
                     f"Got: {data.get('collection_months')}")
            
            log_test('F', 'F2: installments defaults to []', 
                     data.get('installments') == [],
                     f"Got: {data.get('installments')}")
            
            log_test('F', 'F2: due_day_of_month defaults to 15', 
                     data.get('due_day_of_month') == 15,
                     f"Got: {data.get('due_day_of_month')}")
            
            log_test('F', 'F2: is_draft defaults to false', 
                     data.get('is_draft') == False,
                     f"Got: {data.get('is_draft')}")
            
            log_test('F', 'F2: internal_notes preserved', 
                     data.get('internal_notes') == 'test',
                     f"Got: {data.get('internal_notes')}")
        
        # Cleanup: DELETE
        if assign_f_id:
            resp_del = requests.delete(
                f"{BACKEND_URL}/fees/assignments/{assign_f_id}",
                headers=get_headers(token)
            )
            log_test('F', 'F2: Cleanup DELETE assignment', 
                     resp_del.status_code == 200,
                     f"Status: {resp_del.status_code}")
        
    except Exception as e:
        log_test('F', 'Test execution', False, f"Error: {e}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_passed = 0
    total_failed = 0
    
    for section in ['A', 'B', 'C', 'D', 'E', 'F']:
        passed = test_results[section]['passed']
        failed = test_results[section]['failed']
        total = passed + failed
        total_passed += passed
        total_failed += failed
        
        status = "✓ PASS" if failed == 0 else "✗ FAIL"
        print(f"\nSection {section}: {status} ({passed}/{total} tests passed)")
        
        if failed > 0:
            print(f"  Failed tests:")
            for test in test_results[section]['tests']:
                if not test['passed']:
                    print(f"    - {test['name']}")
                    if test['details']:
                        print(f"      {test['details']}")
    
    print(f"\n{'='*80}")
    print(f"OVERALL: {total_passed}/{total_passed + total_failed} tests passed")
    print(f"{'='*80}\n")
    
    return total_passed, total_failed

def main():
    print("="*80)
    print("BACKEND TESTING: Assign Fees Redesign v2 (Jul 2026)")
    print("="*80)
    
    # Login
    print("\n[LOGIN] Authenticating as Super Admin...")
    token = login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    if not token:
        print("❌ Login failed. Cannot proceed with tests.")
        return
    print("✓ Login successful")
    
    # Get fee plan
    print("\n[SETUP] Getting active fee plan...")
    fee_plan_id = get_active_fee_plan(token)
    if not fee_plan_id:
        print("❌ Could not get fee plan. Cannot proceed with tests.")
        return
    print(f"✓ Using fee plan: {fee_plan_id}")
    
    # Run tests
    assign_a_id = test_section_a(token, fee_plan_id)
    test_section_b(token, fee_plan_id, assign_a_id)
    test_section_c(token, fee_plan_id)
    test_section_d(token, fee_plan_id)
    test_section_e(token, fee_plan_id)
    test_section_f(token, fee_plan_id)
    
    # Print summary
    total_passed, total_failed = print_summary()
    
    # Exit with appropriate code
    if total_failed > 0:
        exit(1)
    else:
        exit(0)

if __name__ == "__main__":
    main()
