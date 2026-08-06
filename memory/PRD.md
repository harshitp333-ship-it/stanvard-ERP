# Stanvard School ERP — PRD

## Original Problem Statement
Add flexible, configurable discount options to the **Global Fee Plan setup** (applies to a whole plan/class), so admins can bake discounts directly into a plan definition instead of applying them ad-hoc at collection time. These plan-baked discounts do **NOT** go through the Owner approval flow, and flow automatically into student fee schedules, the Parent portal (Pay Monthly / Pay Fully) and receipts.

Base app: existing React + FastAPI + MongoDB ERP imported from https://github.com/anayacreativesin-blip/stanvard-by-anaya.git

## Architecture
- Backend: FastAPI (`/app/backend/server.py`, models in `models.py`), MongoDB (motor). All routes prefixed `/api`.
- Frontend: React + shadcn/ui + Tailwind. Fee plan UI in `src/pages/FeesStructure.jsx`; parent pay in `src/pages/parent/ParentPay.jsx`.
- Auth: JWT (roles: super_admin, school_admin, accountant, teacher, parent). Seeded via `seed.py`.

## User Personas
- School Admin / Accountant: define fee heads, fee plans (now with discounts), assign to students, collect fees.
- Owner (super_admin): approves student-level ad-hoc discounts (unchanged).
- Parent: views child's monthly/annual fees, pays online, downloads receipts.

## Core Requirements (static)
- Plan-baked discounts: plan-level flat/percent, yearly/full-session flat/percent, per-month flat/percent.
- No owner approval for plan-baked discounts.
- Student-level ad-hoc discounts + owner approval flow remain untouched.
- Backward compatible: all new fields optional; existing plans keep working.

## Implemented (2026-08-06)
- **Model** (`models.py`): `FeePlan`/`FeePlanCreate` extended with `plan_discount_type/value`, `yearly_discount_type/value`, `month_discounts[]`, `installment_discounts[]`; new `PlanMonthDiscount`.
- **Discount helper** (`server.py`): `compute_plan_discount_breakdown`, `_discount_amount`, `_plan_month_discount_map`, `_validate_plan_discounts`. Documented resolution priority: plan-level → yearly (both reduce annual gross) → split across active months → per-month discounts reduce individual months (no double-applying).
- **Endpoints**: `POST /api/fees/plans` + `PATCH /api/fees/plans/{id}` persist + validate new fields (percent 0–100, month 1–12, no negatives → 400).
- **Wiring**: `student_fee_schedule` and `student_dues` apply plan-baked discounts; fee-schedule returns `plan_discount_total`, `plan_lump_discount`, `month_discount_total`, `you_saved`; per-month installments reflect month discounts.
- **Frontend**: Fee Plan dialog "Discounts" card (plan-level + yearly toggles, month builder with add/remove chips, live per-month + annual net preview + "You save %"). Plans table shows discount badges. ParentPay shows "You saved ₹X" banner + "Plan discount" line in Pay Full.
- **Unit tests**: `backend/test_discount_helper.py` (6/6 pass). Testing agent iteration_10: no defects; backend 10/10, frontend all critical flows pass.
- **Seed fix**: parents were unlinked (`linked_student_id` singular vs `linked_student_ids` list) — fixed seed.py and migrated all 108 parents in DB. Sample plan "Class I 2026-27 (Discount Demo)" set up for parent.gn20250001's child (Pari Sharma) to demo discounts.

## Backlog / Remaining
- P1: Apply plan-baked discounts to admin **reports/collection aggregations** (`server.py` ~2400/2500/3200) for full consistency in analytics (fee-schedule & dues already done).
- P2: Handle multiple concurrent plans per student for lump discounts (currently primary/first plan drives plan-level discount).
- P2: Optionally seed `linked_student_ids` cleanly on next fresh seed (code fixed; existing DB migrated).

## Test Credentials
See `/app/memory/test_credentials.md`.
