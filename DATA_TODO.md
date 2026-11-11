# DATA_TODO.md – Owner Verification Checklist

This file lists curated data items that must be reviewed and verified by the project owner before deploying to real users.

Run the validator at any time:
```bash
python -m scripts.check_data
```

## 1. Helplines (`data/helplines.json`)
- [ ] Emergency 112 – Verify state-level routing
- [ ] Women Helpline 181 – Verify operational hours
- [ ] Childline 1098 – Verify integration with 112
- [ ] Cyber Fraud 1930 – Verify operational hours & portal
- [ ] Senior Citizens 14567 – Verify coverage
- [ ] Mental Health 14416 (Tele-MANAS) – Verify toll-free availability

## 2. Allowlists (`data/allowlists.json`)
- [ ] Official scheme domain list (add any state-specific portal URLs)
- [ ] Verified government phone numbers

## 3. Documents Help (`data/documents_help/`)
- [ ] Check issuing authorities, fees, and processing times
- [ ] Confirm valid alternative documents

## 4. Local Offices (`data/offices.json`)
- [ ] Add real local CSC / Panchayat / Tehsil office addresses for target districts

## 5. Rejection & Grievance Data (`data/rejection_reasons/`)
- [ ] Verify standard rejection appeal routes and escalation helplines
