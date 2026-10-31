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
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
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
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(specialization_id) REFERENCES specializations (id)
);


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

CREATE TABLE trainees (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	department_id INTEGER, 
	trainee_type VARCHAR(15) NOT NULL, 
	year_branch VARCHAR(120), 
	supervisor_id INTEGER, 
	phone VARCHAR(30), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(supervisor_id) REFERENCES doctors (id)
);


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
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_appointments_doctor_id ON appointments (doctor_id);
CREATE INDEX ix_appointments_patient_id ON appointments (patient_id);
CREATE INDEX ix_appointments_scheduled_at ON appointments (scheduled_at);

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
	FOREIGN KEY(trainee_id) REFERENCES trainees (id), 
	FOREIGN KEY(verified_by) REFERENCES doctors (id)
);

CREATE INDEX ix_trainee_histories_patient_id ON trainee_histories (patient_id);
CREATE INDEX ix_trainee_histories_status ON trainee_histories (status);
CREATE INDEX ix_trainee_histories_trainee_id ON trainee_histories (trainee_id);

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
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id)
);

CREATE INDEX ix_prescriptions_doctor_id ON prescriptions (doctor_id);
CREATE INDEX ix_prescriptions_patient_id ON prescriptions (patient_id);

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
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	seen_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	supervisor_reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	supervisor_note VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(trainee_id) REFERENCES trainees (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(history_id) REFERENCES trainee_histories (id), 
	FOREIGN KEY(suggested_department_id) REFERENCES departments (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id)
);

CREATE INDEX ix_referrals_doctor_id ON referrals (doctor_id);
CREATE INDEX ix_referrals_history_id ON referrals (history_id);
CREATE INDEX ix_referrals_patient_id ON referrals (patient_id);
CREATE INDEX ix_referrals_status ON referrals (status);
CREATE INDEX ix_referrals_trainee_id ON referrals (trainee_id);

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

CREATE TABLE lab_test_orders (
	id SERIAL NOT NULL, 
	prescription_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	test_name VARCHAR(200) NOT NULL, 
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
	UNIQUE (sample_code), 
	FOREIGN KEY(collected_by) REFERENCES users (id), 
	FOREIGN KEY(completed_by) REFERENCES users (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE INDEX ix_lab_test_orders_patient_id ON lab_test_orders (patient_id);
CREATE INDEX ix_lab_test_orders_prescription_id ON lab_test_orders (prescription_id);
CREATE INDEX ix_lab_test_orders_status ON lab_test_orders (status);

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

