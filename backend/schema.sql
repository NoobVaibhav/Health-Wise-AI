-- Reference PostgreSQL schema, generated from app/database/models.py
-- (the app also creates these tables automatically on startup)

CREATE TABLE branches (
	id SERIAL NOT NULL, 
	code VARCHAR(8) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	address VARCHAR(300), 
	phone VARCHAR(30), 
	email VARCHAR(150), 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);


CREATE TABLE departments (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);


CREATE TABLE diagnostic_tests (
	id SERIAL NOT NULL, 
	kind VARCHAR(10) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	sample_type VARCHAR(40), 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_diagnostic_test UNIQUE (kind, name)
);

CREATE INDEX ix_diagnostic_tests_kind ON diagnostic_tests (kind);

CREATE TABLE medicine_inventory (
	id SERIAL NOT NULL, 
	medicine_name VARCHAR(200) NOT NULL, 
	batch_number VARCHAR(50), 
	quantity INTEGER NOT NULL, 
	expiry_date DATE, 
	manufacture_date DATE, 
	manufacturer VARCHAR(150), 
	unit_price FLOAT, 
	barcode VARCHAR(64), 
	gst_percent FLOAT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_medicine_inventory_barcode ON medicine_inventory (barcode);
CREATE INDEX ix_medicine_inventory_medicine_name ON medicine_inventory (medicine_name);

CREATE TABLE permissions (
	id SERIAL NOT NULL, 
	code VARCHAR(60) NOT NULL, 
	description VARCHAR(300), 
	PRIMARY KEY (id), 
	UNIQUE (code)
);


CREATE TABLE roles (
	id SERIAL NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(300), 
	is_system BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);


CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	must_change_password BOOLEAN NOT NULL, 
	avatar_path VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_role ON users (role);

CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(50) NOT NULL, 
	entity_type VARCHAR(50), 
	entity_id INTEGER, 
	details VARCHAR(300), 
	ip_address VARCHAR(60), 
	timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_timestamp ON audit_logs (timestamp);
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE consultation_templates (
	id SERIAL NOT NULL, 
	department_id INTEGER, 
	name VARCHAR(120) NOT NULL, 
	fields_json TEXT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
);

CREATE INDEX ix_consultation_templates_department_id ON consultation_templates (department_id);

CREATE TABLE diagnostic_analytes (
	id SERIAL NOT NULL, 
	test_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	unit VARCHAR(30), 
	method VARCHAR(100), 
	ref_low FLOAT, 
	ref_high FLOAT, 
	critical_low FLOAT, 
	critical_high FLOAT, 
	sort_order INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_diagnostic_analyte UNIQUE (test_id, name), 
	FOREIGN KEY(test_id) REFERENCES diagnostic_tests (id)
);

CREATE INDEX ix_diagnostic_analytes_test_id ON diagnostic_analytes (test_id);

CREATE TABLE employees (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	designation VARCHAR(100), 
	phone VARCHAR(30), 
	address VARCHAR(300), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);


CREATE TABLE escalation_rules (
	id SERIAL NOT NULL, 
	parameter VARCHAR(20) NOT NULL, 
	comparison VARCHAR(2) NOT NULL, 
	threshold FLOAT NOT NULL, 
	level VARCHAR(8) NOT NULL, 
	message VARCHAR(200) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id)
);

CREATE INDEX ix_escalation_rules_parameter ON escalation_rules (parameter);

CREATE TABLE hospital_profile (
	id SERIAL NOT NULL, 
	name VARCHAR(200), 
	address VARCHAR(300), 
	phone VARCHAR(30), 
	email VARCHAR(150), 
	registration_number VARCHAR(80), 
	gst_number VARCHAR(30), 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);


CREATE TABLE hospital_settings (
	id SERIAL NOT NULL, 
	branch_id INTEGER, 
	key VARCHAR(60) NOT NULL, 
	value VARCHAR(500) NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_by INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_setting_branch_key UNIQUE (branch_id, key), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE INDEX ix_hospital_settings_key ON hospital_settings (key);

CREATE TABLE lab_staff (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	lab_name VARCHAR(150), 
	phone VARCHAR(30), 
	registration_number VARCHAR(50), 
	address VARCHAR(300), 
	staff_type VARCHAR(12), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);


CREATE TABLE number_counters (
	id SERIAL NOT NULL, 
	kind VARCHAR(10) NOT NULL, 
	branch_id INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	last_number INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_number_counter UNIQUE (kind, branch_id, year), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);


CREATE TABLE nurses (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	branch_id INTEGER, 
	designation VARCHAR(100), 
	registration_number VARCHAR(50), 
	phone VARCHAR(30), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);


CREATE TABLE pharmacy_staff (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	pharmacy_name VARCHAR(150), 
	phone VARCHAR(30), 
	license_number VARCHAR(50), 
	address VARCHAR(300), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);


CREATE TABLE radiology_staff (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	staff_type VARCHAR(12) NOT NULL, 
	phone VARCHAR(30), 
	registration_number VARCHAR(50), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);


CREATE TABLE role_permissions (
	id SERIAL NOT NULL, 
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	FOREIGN KEY(permission_id) REFERENCES permissions (id)
);

CREATE INDEX ix_role_permissions_permission_id ON role_permissions (permission_id);
CREATE INDEX ix_role_permissions_role_id ON role_permissions (role_id);

CREATE TABLE service_catalog (
	id SERIAL NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	category VARCHAR(20) NOT NULL, 
	department_id INTEGER, 
	price FLOAT NOT NULL, 
	gst_percent FLOAT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
);

CREATE INDEX ix_service_catalog_category ON service_catalog (category);
CREATE INDEX ix_service_catalog_name ON service_catalog (name);

CREATE TABLE specializations (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	name_key VARCHAR(100) NOT NULL, 
	department_id INTEGER NOT NULL, 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_specialization_department_name UNIQUE (department_id, name_key), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
);

CREATE INDEX ix_specializations_department_id ON specializations (department_id);

CREATE TABLE uhid_counters (
	id SERIAL NOT NULL, 
	branch_id INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	last_number INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_uhid_counter UNIQUE (branch_id, year), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);


CREATE TABLE user_roles (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	granted_by INTEGER, 
	granted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_role UNIQUE (user_id, role_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	FOREIGN KEY(granted_by) REFERENCES users (id)
);

CREATE INDEX ix_user_roles_user_id ON user_roles (user_id);

CREATE TABLE wards (
	id SERIAL NOT NULL, 
	branch_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	ward_type VARCHAR(14) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ward_name UNIQUE (branch_id, name), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);


CREATE TABLE doctors (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	department_id INTEGER, 
	specialization VARCHAR(120), 
	specialization_id INTEGER, 
	phone VARCHAR(30), 
	qualification VARCHAR(150), 
	registration_number VARCHAR(50), 
	experience_years INTEGER, 
	grade VARCHAR(16), 
	pg_year INTEGER, 
	pg_branch VARCHAR(120), 
	supervisor_id INTEGER, 
	can_prescribe_independently BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(specialization_id) REFERENCES specializations (id), 
	FOREIGN KEY(supervisor_id) REFERENCES doctors (id)
);

CREATE INDEX ix_doctors_grade ON doctors (grade);

CREATE TABLE patients (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	patient_code VARCHAR(20) NOT NULL, 
	date_of_birth DATE, 
	gender VARCHAR(30), 
	phone VARCHAR(30), 
	address VARCHAR(300), 
	emergency_contact VARCHAR(150), 
	blood_group VARCHAR(10), 
	allergies TEXT, 
	medical_history_text TEXT, 
	current_medications TEXT, 
	assigned_doctor_id INTEGER, 
	uhid VARCHAR(30), 
	branch_id INTEGER, 
	abha_id VARCHAR(20), 
	merged_into_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(assigned_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(merged_into_id) REFERENCES patients (id)
);

CREATE UNIQUE INDEX ix_patients_patient_code ON patients (patient_code);
CREATE UNIQUE INDEX ix_patients_uhid ON patients (uhid);

CREATE TABLE beds (
	id SERIAL NOT NULL, 
	ward_id INTEGER NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	reserved_for_patient_id INTEGER, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bed_code UNIQUE (ward_id, code), 
	FOREIGN KEY(ward_id) REFERENCES wards (id), 
	FOREIGN KEY(reserved_for_patient_id) REFERENCES patients (id)
);

CREATE INDEX ix_beds_status ON beds (status);
CREATE INDEX ix_beds_ward_id ON beds (ward_id);

CREATE TABLE break_glass_grants (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	reason VARCHAR(500) NOT NULL, 
	granted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	review_note VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id)
);

CREATE INDEX ix_break_glass_grants_expires_at ON break_glass_grants (expires_at);
CREATE INDEX ix_break_glass_grants_patient_id ON break_glass_grants (patient_id);
CREATE INDEX ix_break_glass_grants_user_id ON break_glass_grants (user_id);

CREATE TABLE chronic_conditions (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	kind VARCHAR(15) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	diagnosis_type VARCHAR(60), 
	duration_text VARCHAR(60), 
	diagnosis_year INTEGER, 
	control_status VARCHAR(20), 
	details_json TEXT, 
	notes TEXT, 
	on_treatment BOOLEAN, 
	source VARCHAR(20) NOT NULL, 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_deleted BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(verified_by) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE INDEX ix_chronic_conditions_patient_id ON chronic_conditions (patient_id);

CREATE TABLE clinical_assessments (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	chief_complaint TEXT, 
	history_of_present_illness TEXT, 
	vitals_json TEXT, 
	examination_json TEXT, 
	provisional_diagnosis TEXT, 
	investigations_advised TEXT, 
	plan_type VARCHAR(20), 
	plan_details TEXT, 
	special_note TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id)
);

CREATE INDEX ix_clinical_assessments_patient_id ON clinical_assessments (patient_id);

CREATE TABLE clinical_summary_snapshots (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	generated_by INTEGER NOT NULL, 
	kind VARCHAR(10) NOT NULL, 
	model VARCHAR(80), 
	content_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(generated_by) REFERENCES doctors (id)
);

CREATE INDEX ix_clinical_summary_snapshots_patient_id ON clinical_summary_snapshots (patient_id);

CREATE TABLE countersign_requests (
	id SERIAL NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	item_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	requested_by INTEGER NOT NULL, 
	supervisor_id INTEGER, 
	status VARCHAR(10) NOT NULL, 
	summary VARCHAR(300), 
	original_json TEXT, 
	comment VARCHAR(500), 
	decided_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	decided_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(requested_by) REFERENCES doctors (id), 
	FOREIGN KEY(supervisor_id) REFERENCES doctors (id), 
	FOREIGN KEY(decided_by) REFERENCES doctors (id)
);

CREATE INDEX ix_countersign_requests_item_id ON countersign_requests (item_id);
CREATE INDEX ix_countersign_requests_kind ON countersign_requests (kind);
CREATE INDEX ix_countersign_requests_patient_id ON countersign_requests (patient_id);
CREATE INDEX ix_countersign_requests_requested_by ON countersign_requests (requested_by);
CREATE INDEX ix_countersign_requests_status ON countersign_requests (status);
CREATE INDEX ix_countersign_requests_supervisor_id ON countersign_requests (supervisor_id);

CREATE TABLE emergency_events (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	recorded_by INTEGER NOT NULL, 
	event_at TIMESTAMP WITHOUT TIME ZONE, 
	arrival_method VARCHAR(40), 
	chief_complaint TEXT, 
	symptoms_json TEXT, 
	onset_text VARCHAR(120), 
	duration_text VARCHAR(120), 
	vitals_json TEXT, 
	recent_medication_changes TEXT, 
	exam_findings TEXT, 
	investigations_ordered TEXT, 
	investigation_results TEXT, 
	clinician_assessment TEXT, 
	documented_cause TEXT, 
	contributing_json TEXT, 
	treatment_given TEXT, 
	response_to_treatment TEXT, 
	disposition VARCHAR(20), 
	discharge_instructions TEXT, 
	follow_up_recommendations TEXT, 
	treating_clinician VARCHAR(150), 
	source_report_ids_json TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(recorded_by) REFERENCES doctors (id)
);

CREATE INDEX ix_emergency_events_patient_id ON emergency_events (patient_id);

CREATE TABLE encounters (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	branch_id INTEGER, 
	department_id INTEGER, 
	type VARCHAR(5) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	source VARCHAR(25), 
	attending_doctor_id INTEGER, 
	appointment_id INTEGER, 
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ended_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(attending_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_encounters_attending_doctor_id ON encounters (attending_doctor_id);
CREATE INDEX ix_encounters_patient_id ON encounters (patient_id);
CREATE INDEX ix_encounters_started_at ON encounters (started_at);
CREATE INDEX ix_encounters_status ON encounters (status);
CREATE INDEX ix_encounters_type ON encounters (type);

CREATE TABLE follow_up_tasks (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	created_by INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	details TEXT, 
	due_date DATE, 
	source_type VARCHAR(30), 
	source_id INTEGER, 
	status VARCHAR(20) NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	outcome TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(created_by) REFERENCES doctors (id)
);

CREATE INDEX ix_follow_up_tasks_patient_id ON follow_up_tasks (patient_id);

CREATE TABLE health_reports (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	uploaded_by INTEGER NOT NULL, 
	assigned_doctor_id INTEGER, 
	filename VARCHAR(255) NOT NULL, 
	file_path VARCHAR(500), 
	report_date DATE, 
	uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	processing_status VARCHAR(20) NOT NULL, 
	doctor_review_status VARCHAR(20) NOT NULL, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	review_decision VARCHAR(20), 
	review_comment TEXT, 
	extracted_text TEXT, 
	processing_method VARCHAR(20), 
	ai_summary TEXT, 
	report_type VARCHAR(30), 
	insights_json TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id), 
	FOREIGN KEY(assigned_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(reviewed_by) REFERENCES doctors (id)
);

CREATE INDEX ix_health_reports_assigned_doctor_id ON health_reports (assigned_doctor_id);
CREATE INDEX ix_health_reports_patient_id ON health_reports (patient_id);

CREATE TABLE history_revisions (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	entity_type VARCHAR(20) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	action VARCHAR(12) NOT NULL, 
	before_json TEXT, 
	changed_by INTEGER, 
	changed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(changed_by) REFERENCES users (id)
);

CREATE INDEX ix_history_revisions_entity_id ON history_revisions (entity_id);
CREATE INDEX ix_history_revisions_entity_type ON history_revisions (entity_type);
CREATE INDEX ix_history_revisions_patient_id ON history_revisions (patient_id);

CREATE TABLE hospital_admissions (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	hospital_name VARCHAR(200), 
	admitted_at TIMESTAMP WITHOUT TIME ZONE, 
	admitted_date_text VARCHAR(40), 
	discharged_at TIMESTAMP WITHOUT TIME ZONE, 
	admission_type VARCHAR(15), 
	main_complaint TEXT, 
	secondary_complaints TEXT, 
	provisional_diagnosis TEXT, 
	final_diagnosis TEXT, 
	reason TEXT, 
	referred_by VARCHAR(200), 
	symptoms TEXT, 
	history_of_present_illness TEXT, 
	preexisting_conditions TEXT, 
	vitals_json TEXT, 
	exam_findings TEXT, 
	investigations TEXT, 
	complications TEXT, 
	treatment_given TEXT, 
	medications_json TEXT, 
	iv_fluids_oxygen TEXT, 
	procedures_supportive TEXT, 
	medication_changes TEXT, 
	response_to_treatment TEXT, 
	stay_complications TEXT, 
	discharge_condition TEXT, 
	treatment_completed TEXT, 
	discharge_medications_json TEXT, 
	discharge_instructions TEXT, 
	wound_rehab_instructions TEXT, 
	followup_date DATE, 
	specialist_review VARCHAR(200), 
	recovery_status TEXT, 
	remaining_symptoms TEXT, 
	readmission_notes TEXT, 
	source VARCHAR(20) NOT NULL, 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_deleted BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(verified_by) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE INDEX ix_hospital_admissions_patient_id ON hospital_admissions (patient_id);

CREATE TABLE medical_history (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	entry_date DATE NOT NULL, 
	entry_type VARCHAR(40) NOT NULL, 
	description TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id)
);

CREATE INDEX ix_medical_history_patient_id ON medical_history (patient_id);

CREATE TABLE patient_assistant_conversations (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
);

CREATE INDEX ix_patient_assistant_conversations_patient_id ON patient_assistant_conversations (patient_id);
CREATE INDEX ix_patient_assistant_conversations_updated_at ON patient_assistant_conversations (updated_at);

CREATE TABLE patient_consents (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	granted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	recorded_by INTEGER, 
	given_by VARCHAR(150), 
	note VARCHAR(300), 
	withdrawn_at TIMESTAMP WITHOUT TIME ZONE, 
	withdrawn_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(recorded_by) REFERENCES users (id), 
	FOREIGN KEY(withdrawn_by) REFERENCES users (id)
);

CREATE INDEX ix_patient_consents_kind ON patient_consents (kind);
CREATE INDEX ix_patient_consents_patient_id ON patient_consents (patient_id);

CREATE TABLE patient_history (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	height_cm FLOAT, 
	weight_kg FLOAT, 
	data_json TEXT, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ix_patient_history_patient_id ON patient_history (patient_id);

CREATE TABLE patient_insurance (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	insurer_name VARCHAR(150) NOT NULL, 
	tpa_name VARCHAR(150), 
	policy_number VARCHAR(60) NOT NULL, 
	member_id VARCHAR(60), 
	valid_from DATE, 
	valid_to DATE, 
	is_active BOOLEAN NOT NULL, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_patient_insurance_patient_id ON patient_insurance (patient_id);

CREATE TABLE patient_merges (
	id SERIAL NOT NULL, 
	kept_patient_id INTEGER NOT NULL, 
	merged_patient_id INTEGER NOT NULL, 
	merged_by INTEGER NOT NULL, 
	reason VARCHAR(500) NOT NULL, 
	moved_json TEXT, 
	merged_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(kept_patient_id) REFERENCES patients (id), 
	FOREIGN KEY(merged_patient_id) REFERENCES patients (id), 
	FOREIGN KEY(merged_by) REFERENCES users (id)
);

CREATE INDEX ix_patient_merges_kept_patient_id ON patient_merges (kept_patient_id);
CREATE INDEX ix_patient_merges_merged_patient_id ON patient_merges (merged_patient_id);

CREATE TABLE summary_reviews (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	item_key VARCHAR(80) NOT NULL, 
	action VARCHAR(20) NOT NULL, 
	text TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id)
);

CREATE INDEX ix_summary_reviews_item_key ON summary_reviews (item_key);
CREATE INDEX ix_summary_reviews_patient_id ON summary_reviews (patient_id);

CREATE TABLE trainee_histories (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	trainee_id INTEGER NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	data_json TEXT, 
	doctor_notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(trainee_id) REFERENCES doctors (id), 
	FOREIGN KEY(verified_by) REFERENCES doctors (id)
);

CREATE INDEX ix_trainee_histories_patient_id ON trainee_histories (patient_id);
CREATE INDEX ix_trainee_histories_status ON trainee_histories (status);
CREATE INDEX ix_trainee_histories_trainee_id ON trainee_histories (trainee_id);

CREATE TABLE admissions (
	id SERIAL NOT NULL, 
	admission_no VARCHAR(24) NOT NULL, 
	patient_id INTEGER NOT NULL, 
	branch_id INTEGER, 
	department_id INTEGER, 
	encounter_id INTEGER NOT NULL, 
	source_encounter_id INTEGER, 
	attending_doctor_id INTEGER NOT NULL, 
	admitting_diagnosis VARCHAR(300), 
	status VARCHAR(12) NOT NULL, 
	admitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expected_discharge DATE, 
	discharged_at TIMESTAMP WITHOUT TIME ZONE, 
	discharge_type VARCHAR(12), 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (admission_no), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(source_encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(attending_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_admissions_attending_doctor_id ON admissions (attending_doctor_id);
CREATE INDEX ix_admissions_patient_id ON admissions (patient_id);
CREATE INDEX ix_admissions_status ON admissions (status);
CREATE UNIQUE INDEX uq_one_active_admission ON admissions (patient_id) WHERE status = 'ADMITTED';

CREATE TABLE appointments (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	department_id INTEGER, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reason VARCHAR(300), 
	symptoms_json TEXT, 
	duration VARCHAR(60), 
	details TEXT, 
	status VARCHAR(20) NOT NULL, 
	created_by INTEGER, 
	encounter_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id)
);

CREATE INDEX ix_appointments_doctor_id ON appointments (doctor_id);
CREATE INDEX ix_appointments_patient_id ON appointments (patient_id);
CREATE INDEX ix_appointments_scheduled_at ON appointments (scheduled_at);

CREATE TABLE consultations (
	id SERIAL NOT NULL, 
	encounter_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	template_id INTEGER, 
	complaint TEXT, 
	hpi TEXT, 
	past_history TEXT, 
	family_history TEXT, 
	examination TEXT, 
	assessment TEXT, 
	plan TEXT, 
	advice TEXT, 
	follow_up_date DATE, 
	data_json TEXT, 
	status VARCHAR(10) NOT NULL, 
	signed_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (encounter_id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(template_id) REFERENCES consultation_templates (id)
);

CREATE INDEX ix_consultations_doctor_id ON consultations (doctor_id);
CREATE INDEX ix_consultations_patient_id ON consultations (patient_id);
CREATE INDEX ix_consultations_status ON consultations (status);

CREATE TABLE diagnoses (
	id SERIAL NOT NULL, 
	encounter_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	text VARCHAR(300) NOT NULL, 
	code VARCHAR(20), 
	kind VARCHAR(12) NOT NULL, 
	added_by INTEGER NOT NULL, 
	added_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(added_by) REFERENCES doctors (id)
);

CREATE INDEX ix_diagnoses_encounter_id ON diagnoses (encounter_id);
CREATE INDEX ix_diagnoses_patient_id ON diagnoses (patient_id);

CREATE TABLE doctor_notes (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	report_id INTEGER, 
	note TEXT NOT NULL, 
	priority VARCHAR(25) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id)
);

CREATE INDEX ix_doctor_notes_patient_id ON doctor_notes (patient_id);

CREATE TABLE doctor_recommendations (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	report_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	recommendation TEXT NOT NULL, 
	follow_up_date DATE, 
	priority VARCHAR(25) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id)
);

CREATE INDEX ix_doctor_recommendations_patient_id ON doctor_recommendations (patient_id);

CREATE TABLE emergency_timeline_entries (
	id SERIAL NOT NULL, 
	event_id INTEGER NOT NULL, 
	occurred_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	text TEXT NOT NULL, 
	recorded_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES emergency_events (id), 
	FOREIGN KEY(recorded_by) REFERENCES doctors (id)
);

CREATE INDEX ix_emergency_timeline_entries_event_id ON emergency_timeline_entries (event_id);

CREATE TABLE encounter_charges (
	id SERIAL NOT NULL, 
	encounter_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	service_id INTEGER, 
	description VARCHAR(200) NOT NULL, 
	amount FLOAT NOT NULL, 
	gst_percent FLOAT NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(service_id) REFERENCES service_catalog (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_encounter_charges_encounter_id ON encounter_charges (encounter_id);
CREATE INDEX ix_encounter_charges_patient_id ON encounter_charges (patient_id);

CREATE TABLE health_parameters (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	test_name VARCHAR(200) NOT NULL, 
	normalized_name VARCHAR(100) NOT NULL, 
	value FLOAT NOT NULL, 
	unit VARCHAR(50), 
	reference_text VARCHAR(120), 
	reference_low FLOAT, 
	reference_high FLOAT, 
	status VARCHAR(20) NOT NULL, 
	ai_explanation TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id)
);

CREATE INDEX ix_health_parameters_normalized_name ON health_parameters (normalized_name);
CREATE INDEX ix_health_parameters_report_id ON health_parameters (report_id);

CREATE TABLE patient_assistant_messages (
	id SERIAL NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	text TEXT NOT NULL, 
	meta_json TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES patient_assistant_conversations (id)
);

CREATE INDEX ix_patient_assistant_messages_conversation_id ON patient_assistant_messages (conversation_id);

CREATE TABLE patient_medications (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	dose VARCHAR(100), 
	frequency VARCHAR(100), 
	reason VARCHAR(200), 
	since VARCHAR(60), 
	notes VARCHAR(300), 
	is_current BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	route VARCHAR(40), 
	prescriber VARCHAR(150), 
	adherence VARCHAR(20), 
	condition_id INTEGER, 
	source VARCHAR(20), 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	is_deleted BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(condition_id) REFERENCES chronic_conditions (id), 
	FOREIGN KEY(verified_by) REFERENCES doctors (id)
);

CREATE INDEX ix_patient_medications_patient_id ON patient_medications (patient_id);

CREATE TABLE prescriptions (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	report_id INTEGER, 
	prescription_date DATE NOT NULL, 
	clinical_indication VARCHAR(300), 
	status VARCHAR(25) NOT NULL, 
	notes TEXT, 
	tests_advised TEXT, 
	encounter_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id)
);

CREATE INDEX ix_prescriptions_doctor_id ON prescriptions (doctor_id);
CREATE INDEX ix_prescriptions_encounter_id ON prescriptions (encounter_id);
CREATE INDEX ix_prescriptions_patient_id ON prescriptions (patient_id);

CREATE TABLE queue_tokens (
	id SERIAL NOT NULL, 
	encounter_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	branch_id INTEGER, 
	token_date DATE NOT NULL, 
	number INTEGER NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	urgent BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	called_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_token_number UNIQUE (doctor_id, token_date, number), 
	UNIQUE (encounter_id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);

CREATE INDEX ix_queue_tokens_doctor_id ON queue_tokens (doctor_id);
CREATE INDEX ix_queue_tokens_status ON queue_tokens (status);
CREATE INDEX ix_queue_tokens_token_date ON queue_tokens (token_date);

CREATE TABLE referral_requests (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	from_encounter_id INTEGER, 
	from_doctor_id INTEGER NOT NULL, 
	to_department_id INTEGER NOT NULL, 
	to_doctor_id INTEGER, 
	reason VARCHAR(500) NOT NULL, 
	urgency VARCHAR(8) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	response_note TEXT, 
	consult_encounter_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	responded_by INTEGER, 
	responded_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(from_encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(from_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(to_department_id) REFERENCES departments (id), 
	FOREIGN KEY(to_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(consult_encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(responded_by) REFERENCES doctors (id)
);

CREATE INDEX ix_referral_requests_from_doctor_id ON referral_requests (from_doctor_id);
CREATE INDEX ix_referral_requests_patient_id ON referral_requests (patient_id);
CREATE INDEX ix_referral_requests_status ON referral_requests (status);
CREATE INDEX ix_referral_requests_to_department_id ON referral_requests (to_department_id);
CREATE INDEX ix_referral_requests_to_doctor_id ON referral_requests (to_doctor_id);

CREATE TABLE report_comparisons (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	previous_report_id INTEGER NOT NULL, 
	latest_report_id INTEGER NOT NULL, 
	result_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(previous_report_id) REFERENCES health_reports (id), 
	FOREIGN KEY(latest_report_id) REFERENCES health_reports (id)
);

CREATE INDEX ix_report_comparisons_patient_id ON report_comparisons (patient_id);

CREATE TABLE surgery_records (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	admission_id INTEGER, 
	procedure_name VARCHAR(200) NOT NULL, 
	reason TEXT, 
	body_site VARCHAR(150), 
	operation_date DATE, 
	operation_year INTEGER, 
	surgeon VARCHAR(150), 
	hospital VARCHAR(200), 
	anesthesia VARCHAR(100), 
	findings TEXT, 
	implant_used BOOLEAN, 
	implant_type VARCHAR(100), 
	implant_material VARCHAR(150), 
	implant_serial VARCHAR(100), 
	postop_xray TEXT, 
	postop_treatment TEXT, 
	postop_complications TEXT, 
	recovery_progress TEXT, 
	source VARCHAR(20) NOT NULL, 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_deleted BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(admission_id) REFERENCES hospital_admissions (id), 
	FOREIGN KEY(verified_by) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE INDEX ix_surgery_records_admission_id ON surgery_records (admission_id);
CREATE INDEX ix_surgery_records_patient_id ON surgery_records (patient_id);

CREATE TABLE trainee_history_revisions (
	id SERIAL NOT NULL, 
	history_id INTEGER NOT NULL, 
	changed_by INTEGER, 
	data_json TEXT, 
	changed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(history_id) REFERENCES trainee_histories (id), 
	FOREIGN KEY(changed_by) REFERENCES users (id)
);

CREATE INDEX ix_trainee_history_revisions_history_id ON trainee_history_revisions (history_id);

CREATE TABLE admission_staff (
	id SERIAL NOT NULL, 
	admission_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	from_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	to_at TIMESTAMP WITHOUT TIME ZONE, 
	assigned_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(assigned_by) REFERENCES users (id)
);

CREATE INDEX ix_admission_staff_admission_id ON admission_staff (admission_id);
CREATE INDEX ix_admission_staff_user_id ON admission_staff (user_id);

CREATE TABLE bed_assignments (
	id SERIAL NOT NULL, 
	admission_id INTEGER NOT NULL, 
	bed_id INTEGER NOT NULL, 
	assigned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	released_at TIMESTAMP WITHOUT TIME ZONE, 
	assigned_by INTEGER, 
	reason VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(bed_id) REFERENCES beds (id), 
	FOREIGN KEY(assigned_by) REFERENCES users (id)
);

CREATE INDEX ix_bed_assignments_admission_id ON bed_assignments (admission_id);
CREATE INDEX ix_bed_assignments_bed_id ON bed_assignments (bed_id);
CREATE UNIQUE INDEX uq_admission_one_bed ON bed_assignments (admission_id) WHERE released_at IS NULL;
CREATE UNIQUE INDEX uq_bed_one_active ON bed_assignments (bed_id) WHERE released_at IS NULL;

CREATE TABLE clinical_orders (
	id SERIAL NOT NULL, 
	encounter_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	admission_id INTEGER, 
	kind VARCHAR(12) NOT NULL, 
	text VARCHAR(300) NOT NULL, 
	priority VARCHAR(8) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	ordered_by INTEGER NOT NULL, 
	ordered_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_by INTEGER, 
	note VARCHAR(300), 
	PRIMARY KEY (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(ordered_by) REFERENCES users (id), 
	FOREIGN KEY(completed_by) REFERENCES users (id)
);

CREATE INDEX ix_clinical_orders_admission_id ON clinical_orders (admission_id);
CREATE INDEX ix_clinical_orders_encounter_id ON clinical_orders (encounter_id);
CREATE INDEX ix_clinical_orders_kind ON clinical_orders (kind);
CREATE INDEX ix_clinical_orders_patient_id ON clinical_orders (patient_id);
CREATE INDEX ix_clinical_orders_status ON clinical_orders (status);

CREATE TABLE consultation_addenda (
	id SERIAL NOT NULL, 
	consultation_id INTEGER NOT NULL, 
	text TEXT NOT NULL, 
	added_by INTEGER NOT NULL, 
	added_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(added_by) REFERENCES users (id)
);

CREATE INDEX ix_consultation_addenda_consultation_id ON consultation_addenda (consultation_id);

CREATE TABLE discharge_summaries (
	id SERIAL NOT NULL, 
	admission_id INTEGER NOT NULL, 
	final_diagnosis TEXT, 
	hospital_course TEXT, 
	procedures TEXT, 
	investigations_summary TEXT, 
	discharge_medicines TEXT, 
	follow_up TEXT, 
	diet_advice TEXT, 
	warning_signs TEXT, 
	status VARCHAR(10) NOT NULL, 
	prepared_by INTEGER, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (admission_id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(prepared_by) REFERENCES doctors (id), 
	FOREIGN KEY(approved_by) REFERENCES doctors (id)
);


CREATE TABLE ed_visits (
	id SERIAL NOT NULL, 
	encounter_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	arrival_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	arrival_mode VARCHAR(12), 
	chief_complaint VARCHAR(300), 
	triage_category INTEGER, 
	triaged_by INTEGER, 
	triaged_at TIMESTAMP WITHOUT TIME ZONE, 
	assigned_doctor_id INTEGER, 
	status VARCHAR(12) NOT NULL, 
	disposition VARCHAR(12), 
	disposition_at TIMESTAMP WITHOUT TIME ZONE, 
	disposition_note VARCHAR(500), 
	admission_id INTEGER, 
	unidentified BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (encounter_id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(triaged_by) REFERENCES users (id), 
	FOREIGN KEY(assigned_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id)
);

CREATE INDEX ix_ed_visits_arrival_at ON ed_visits (arrival_at);
CREATE INDEX ix_ed_visits_assigned_doctor_id ON ed_visits (assigned_doctor_id);
CREATE INDEX ix_ed_visits_patient_id ON ed_visits (patient_id);
CREATE INDEX ix_ed_visits_status ON ed_visits (status);
CREATE INDEX ix_ed_visits_triage_category ON ed_visits (triage_category);

CREATE TABLE intake_output (
	id SERIAL NOT NULL, 
	admission_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	kind VARCHAR(6) NOT NULL, 
	item VARCHAR(100) NOT NULL, 
	amount_ml INTEGER NOT NULL, 
	recorded_by INTEGER NOT NULL, 
	recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(recorded_by) REFERENCES users (id)
);

CREATE INDEX ix_intake_output_admission_id ON intake_output (admission_id);
CREATE INDEX ix_intake_output_patient_id ON intake_output (patient_id);

CREATE TABLE medication_orders (
	id SERIAL NOT NULL, 
	admission_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	medicine_name VARCHAR(200) NOT NULL, 
	dose VARCHAR(100) NOT NULL, 
	route VARCHAR(40), 
	times VARCHAR(100) NOT NULL, 
	instructions VARCHAR(300), 
	start_date DATE NOT NULL, 
	end_date DATE, 
	status VARCHAR(10) NOT NULL, 
	ordered_by INTEGER NOT NULL, 
	ordered_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	stopped_by INTEGER, 
	stopped_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(ordered_by) REFERENCES doctors (id), 
	FOREIGN KEY(stopped_by) REFERENCES doctors (id)
);

CREATE INDEX ix_medication_orders_admission_id ON medication_orders (admission_id);
CREATE INDEX ix_medication_orders_patient_id ON medication_orders (patient_id);
CREATE INDEX ix_medication_orders_status ON medication_orders (status);

CREATE TABLE nursing_notes (
	id SERIAL NOT NULL, 
	admission_id INTEGER, 
	encounter_id INTEGER, 
	patient_id INTEGER NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	shift VARCHAR(10), 
	text TEXT NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_nursing_notes_admission_id ON nursing_notes (admission_id);
CREATE INDEX ix_nursing_notes_encounter_id ON nursing_notes (encounter_id);
CREATE INDEX ix_nursing_notes_patient_id ON nursing_notes (patient_id);

CREATE TABLE patient_assistant_evidence (
	id SERIAL NOT NULL, 
	message_id INTEGER NOT NULL, 
	source_type VARCHAR(20) NOT NULL, 
	source_id INTEGER, 
	label VARCHAR(200) NOT NULL, 
	record_date VARCHAR(20), 
	PRIMARY KEY (id), 
	FOREIGN KEY(message_id) REFERENCES patient_assistant_messages (id)
);

CREATE INDEX ix_patient_assistant_evidence_message_id ON patient_assistant_evidence (message_id);

CREATE TABLE prescription_items (
	id SERIAL NOT NULL, 
	prescription_id INTEGER NOT NULL, 
	medicine_name VARCHAR(200) NOT NULL, 
	dosage VARCHAR(100) NOT NULL, 
	frequency VARCHAR(100) NOT NULL, 
	duration VARCHAR(100) NOT NULL, 
	quantity INTEGER NOT NULL, 
	instructions TEXT, 
	dispense_status VARCHAR(25) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id)
);

CREATE INDEX ix_prescription_items_prescription_id ON prescription_items (prescription_id);

CREATE TABLE progress_notes (
	id SERIAL NOT NULL, 
	admission_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	note TEXT NOT NULL, 
	corrects_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(corrects_id) REFERENCES progress_notes (id)
);

CREATE INDEX ix_progress_notes_admission_id ON progress_notes (admission_id);
CREATE INDEX ix_progress_notes_patient_id ON progress_notes (patient_id);

CREATE TABLE referrals (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	trainee_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	history_id INTEGER NOT NULL, 
	reason VARCHAR(300) NOT NULL, 
	urgent BOOLEAN NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	suggested_department_id INTEGER, 
	overridden BOOLEAN NOT NULL, 
	appointment_id INTEGER, 
	encounter_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	seen_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	supervisor_reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	supervisor_note VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(trainee_id) REFERENCES doctors (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(history_id) REFERENCES trainee_histories (id), 
	FOREIGN KEY(suggested_department_id) REFERENCES departments (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id)
);

CREATE INDEX ix_referrals_doctor_id ON referrals (doctor_id);
CREATE INDEX ix_referrals_history_id ON referrals (history_id);
CREATE INDEX ix_referrals_patient_id ON referrals (patient_id);
CREATE INDEX ix_referrals_status ON referrals (status);
CREATE INDEX ix_referrals_trainee_id ON referrals (trainee_id);

CREATE TABLE sales (
	id SERIAL NOT NULL, 
	bill_number VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	pharmacy_staff_id INTEGER NOT NULL, 
	prescription_id INTEGER, 
	customer_name VARCHAR(150), 
	customer_phone VARCHAR(30), 
	payment_method VARCHAR(10) NOT NULL, 
	subtotal FLOAT NOT NULL, 
	discount FLOAT NOT NULL, 
	tax FLOAT NOT NULL, 
	total FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pharmacy_staff_id) REFERENCES pharmacy_staff (id), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id)
);

CREATE UNIQUE INDEX ix_sales_bill_number ON sales (bill_number);
CREATE INDEX ix_sales_created_at ON sales (created_at);

CREATE TABLE vital_sets (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	encounter_id INTEGER, 
	admission_id INTEGER, 
	recorded_by INTEGER, 
	recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	pulse INTEGER, 
	bp_systolic INTEGER, 
	bp_diastolic INTEGER, 
	temperature_f FLOAT, 
	resp_rate INTEGER, 
	spo2 INTEGER, 
	weight_kg FLOAT, 
	height_cm FLOAT, 
	pain_score INTEGER, 
	gcs INTEGER, 
	note VARCHAR(300), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(recorded_by) REFERENCES users (id)
);

CREATE INDEX ix_vital_sets_admission_id ON vital_sets (admission_id);
CREATE INDEX ix_vital_sets_encounter_id ON vital_sets (encounter_id);
CREATE INDEX ix_vital_sets_patient_id ON vital_sets (patient_id);
CREATE INDEX ix_vital_sets_recorded_at ON vital_sets (recorded_at);

CREATE TABLE clinical_alerts (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	encounter_id INTEGER, 
	admission_id INTEGER, 
	vital_set_id INTEGER, 
	rule_id INTEGER, 
	level VARCHAR(8) NOT NULL, 
	message VARCHAR(300) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	acknowledged_by INTEGER, 
	acknowledged_at TIMESTAMP WITHOUT TIME ZONE, 
	ack_note VARCHAR(300), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(vital_set_id) REFERENCES vital_sets (id), 
	FOREIGN KEY(rule_id) REFERENCES escalation_rules (id), 
	FOREIGN KEY(acknowledged_by) REFERENCES users (id)
);

CREATE INDEX ix_clinical_alerts_admission_id ON clinical_alerts (admission_id);
CREATE INDEX ix_clinical_alerts_level ON clinical_alerts (level);
CREATE INDEX ix_clinical_alerts_patient_id ON clinical_alerts (patient_id);
CREATE INDEX ix_clinical_alerts_status ON clinical_alerts (status);

CREATE TABLE ed_timeline (
	id SERIAL NOT NULL, 
	ed_visit_id INTEGER NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	text VARCHAR(500) NOT NULL, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ed_visit_id) REFERENCES ed_visits (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_ed_timeline_ed_visit_id ON ed_timeline (ed_visit_id);

CREATE TABLE lab_test_orders (
	id SERIAL NOT NULL, 
	prescription_id INTEGER, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	test_name VARCHAR(200) NOT NULL, 
	clinical_order_id INTEGER, 
	encounter_id INTEGER, 
	test_id INTEGER, 
	assigned_to INTEGER, 
	result_status VARCHAR(16), 
	has_critical BOOLEAN, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	approval_note VARCHAR(500), 
	doctor_seen_at TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(20) NOT NULL, 
	urgent BOOLEAN, 
	sample_type VARCHAR(40), 
	sample_code VARCHAR(30), 
	collected_at TIMESTAMP WITHOUT TIME ZONE, 
	collected_by INTEGER, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_by INTEGER, 
	report_id INTEGER, 
	note TEXT, 
	rejection_reason TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_by INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_lab_order_test UNIQUE (prescription_id, test_name), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	UNIQUE (clinical_order_id), 
	FOREIGN KEY(clinical_order_id) REFERENCES clinical_orders (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(test_id) REFERENCES diagnostic_tests (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id), 
	UNIQUE (sample_code), 
	FOREIGN KEY(collected_by) REFERENCES users (id), 
	FOREIGN KEY(completed_by) REFERENCES users (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE INDEX ix_lab_test_orders_encounter_id ON lab_test_orders (encounter_id);
CREATE INDEX ix_lab_test_orders_patient_id ON lab_test_orders (patient_id);
CREATE INDEX ix_lab_test_orders_prescription_id ON lab_test_orders (prescription_id);
CREATE INDEX ix_lab_test_orders_status ON lab_test_orders (status);

CREATE TABLE mar_entries (
	id SERIAL NOT NULL, 
	medication_order_id INTEGER NOT NULL, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	acted_by INTEGER, 
	acted_at TIMESTAMP WITHOUT TIME ZONE, 
	note VARCHAR(300), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_mar_dose UNIQUE (medication_order_id, scheduled_at), 
	FOREIGN KEY(medication_order_id) REFERENCES medication_orders (id), 
	FOREIGN KEY(acted_by) REFERENCES users (id)
);

CREATE INDEX ix_mar_entries_medication_order_id ON mar_entries (medication_order_id);
CREATE INDEX ix_mar_entries_scheduled_at ON mar_entries (scheduled_at);
CREATE INDEX ix_mar_entries_status ON mar_entries (status);

CREATE TABLE medicine_dispensing (
	id SERIAL NOT NULL, 
	prescription_id INTEGER NOT NULL, 
	prescription_item_id INTEGER NOT NULL, 
	pharmacy_staff_id INTEGER NOT NULL, 
	quantity_prescribed INTEGER NOT NULL, 
	quantity_dispensed INTEGER NOT NULL, 
	dispensed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(25) NOT NULL, 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id), 
	FOREIGN KEY(prescription_item_id) REFERENCES prescription_items (id), 
	FOREIGN KEY(pharmacy_staff_id) REFERENCES pharmacy_staff (id)
);

CREATE INDEX ix_medicine_dispensing_prescription_id ON medicine_dispensing (prescription_id);

CREATE TABLE radiology_orders (
	id SERIAL NOT NULL, 
	clinical_order_id INTEGER, 
	encounter_id INTEGER, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	test_id INTEGER, 
	study VARCHAR(200) NOT NULL, 
	modality VARCHAR(20) NOT NULL, 
	priority VARCHAR(8) NOT NULL, 
	clinical_info VARCHAR(300), 
	status VARCHAR(12) NOT NULL, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE, 
	technician_id INTEGER, 
	radiologist_id INTEGER, 
	performed_at TIMESTAMP WITHOUT TIME ZONE, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	doctor_seen_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (clinical_order_id), 
	FOREIGN KEY(clinical_order_id) REFERENCES clinical_orders (id), 
	FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(test_id) REFERENCES diagnostic_tests (id), 
	FOREIGN KEY(technician_id) REFERENCES users (id), 
	FOREIGN KEY(radiologist_id) REFERENCES users (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);

CREATE INDEX ix_radiology_orders_encounter_id ON radiology_orders (encounter_id);
CREATE INDEX ix_radiology_orders_modality ON radiology_orders (modality);
CREATE INDEX ix_radiology_orders_patient_id ON radiology_orders (patient_id);
CREATE INDEX ix_radiology_orders_status ON radiology_orders (status);

CREATE TABLE sale_items (
	id SERIAL NOT NULL, 
	sale_id INTEGER NOT NULL, 
	inventory_id INTEGER, 
	prescription_item_id INTEGER, 
	medicine_name VARCHAR(200) NOT NULL, 
	batch_number VARCHAR(50), 
	expiry_date DATE, 
	quantity INTEGER NOT NULL, 
	unit_price FLOAT NOT NULL, 
	gst_percent FLOAT NOT NULL, 
	line_total FLOAT NOT NULL, 
	tax_amount FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(inventory_id) REFERENCES medicine_inventory (id), 
	FOREIGN KEY(prescription_item_id) REFERENCES prescription_items (id)
);

CREATE INDEX ix_sale_items_prescription_item_id ON sale_items (prescription_item_id);
CREATE INDEX ix_sale_items_sale_id ON sale_items (sale_id);

CREATE TABLE lab_results (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	analyte_id INTEGER, 
	analyte_name VARCHAR(100) NOT NULL, 
	value_text VARCHAR(100) NOT NULL, 
	value_num FLOAT, 
	unit VARCHAR(30), 
	method VARCHAR(100), 
	ref_low FLOAT, 
	ref_high FLOAT, 
	flag VARCHAR(12) NOT NULL, 
	comment VARCHAR(300), 
	entered_by INTEGER, 
	entered_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES lab_test_orders (id), 
	FOREIGN KEY(analyte_id) REFERENCES diagnostic_analytes (id), 
	FOREIGN KEY(entered_by) REFERENCES users (id)
);

CREATE INDEX ix_lab_results_order_id ON lab_results (order_id);

CREATE TABLE radiology_attachments (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	filename VARCHAR(200) NOT NULL, 
	stored_path VARCHAR(300) NOT NULL, 
	uploaded_by INTEGER NOT NULL, 
	uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES radiology_orders (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id)
);

CREATE INDEX ix_radiology_attachments_order_id ON radiology_attachments (order_id);

CREATE TABLE radiology_reports (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	technique VARCHAR(300), 
	findings TEXT NOT NULL, 
	impression TEXT NOT NULL, 
	reported_by INTEGER NOT NULL, 
	reported_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (order_id), 
	FOREIGN KEY(order_id) REFERENCES radiology_orders (id), 
	FOREIGN KEY(reported_by) REFERENCES users (id)
);


