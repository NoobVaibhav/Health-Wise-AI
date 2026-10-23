# Laboratory workflow

Before, the laboratory role could only read a list of advised tests. Now every advised test is followed from the doctor's order to a reviewed result.

```
doctor advises a test on a prescription
   -> Waiting for the sample  -> Sample taken (a sample code is made)  -> Being tested
   -> Result uploaded (a normal report goes to the prescribing doctor)  -> doctor reviews  -> patient sees it
   A bad sample is Rejected with a reason and can be ordered again (the patient is told to give it again).
```

## What each person sees

| Who | Where | What |
|---|---|---|
| **Laboratory staff** | Work list (`/lab`) | Counts (to do, urgent, done today, longest wait), tabs (To do, Waiting for sample, Sample taken, Being tested, Done, Rejected, All), search by patient, ID, RX code, test or **sample code**. Per test: *Collect the sample* (sample type, code like `LAB-20261023-0001` to write on the sample), *Start testing*, *Upload the result*, *Reject the sample* (reason required), *Order again*, *Mark urgent* (urgent tests come first). The older list is kept as *Tests advised*. |
| **Doctor** | Patient > Reports tab | The progress of that patient's tests, and a link to the result. |
| **Patient** | My Reports | Each test in plain words ("Please go to the laboratory to give the sample", "Your sample is being tested", "The sample could not be used: please give it again"). The result link appears only after the doctor has reviewed it. |
| **Front desk (employee)** | Tests advised / read-only work list | Can look, cannot change anything. |

## Safety rules

* **Wrong-patient guard**: if the name printed on a result is not the patient's, nothing is saved. The lab must read the warning and confirm on purpose ("I checked: upload it for this patient").
* A result can only be added after the sample is taken; a finished test takes no second result; "done" can only happen by uploading a result (it cannot be clicked).
* Unreadable files (empty, fake PDF, executable, text without lab values) are refused with a clear message and the test stays open.
* The result is an ordinary report: analysed by the existing engine, assigned to the prescribing doctor, **not shown to the patient before the doctor reviews it**.
* The lab sees patient name, ID, test, reason and prescription code only: never medicines or other reports. The pharmacy sees nothing of this.
* Cancelling the prescription cancels its open tests. Every status change, urgent mark and result upload is written to the audit log.

## API

Lab staff: `GET /api/lab/dashboard`, `GET /api/lab/worklist?status_filter=&q=&urgent=`, `POST /api/lab/tests/{id}/status`, `POST /api/lab/tests/{id}/urgent`, `POST /api/lab/tests/{id}/result` (file, optional `confirm_mismatch`). Front desk: `GET /api/lab/worklist`, `GET /api/lab/test-orders`. Patient: `GET /api/lab/my-tests`. Doctor: `GET /api/lab/patient/{id}/tests`. A new table `lab_test_orders` is created automatically; work items are made from the tests written on prescriptions the first time anyone looks.

## Tests

`backend/tests/test_lab.py` (10): items made once, workflow order and sample labels, rejection and re-order, result upload to doctor review and patient visibility, wrong-patient result, unreadable files, cancelled prescription, dashboard/search/urgent/audit, permissions, and two requests creating rows at the same moment. Checked in a browser with the lab, patient and doctor accounts.

## Not included yet

Result values typed in by hand (a result must be an uploaded file), per-parameter reference-range setup, printing sample labels or barcodes, and notifying the patient by SMS or email.
