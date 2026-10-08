-- Reference PostgreSQL schema, generated from app/database/models.py
-- (the app also creates these tables automatically on startup)

CREATE TABLE departments (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);


CREATE TABLE medicine_inventory (
	id SERIAL NOT NULL, 
	medicine_name VARCHAR(200) NOT NULL, 
	batch_number VARCHAR(50), 
	quantity INTEGER NOT NULL, 
	expiry_date DATE, 
	manufacturer VARCHAR(150), 
	unit_price FLOAT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_medicine_inventory_medicine_name ON medicine_inventory (medicine_name);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	must_change_password BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_users_role ON users (role);
CREATE UNIQUE INDEX ix_users_email ON users (email);

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

CREATE TABLE doctors (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	department_id INTEGER, 
	specialization VARCHAR(120), 
	phone VARCHAR(30), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
);


CREATE TABLE employees (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	designation VARCHAR(100), 
	phone VARCHAR(30), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);


CREATE TABLE pharmacy_staff (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	pharmacy_name VARCHAR(150), 
	phone VARCHAR(30), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
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
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(assigned_doctor_id) REFERENCES doctors (id)
);

CREATE UNIQUE INDEX ix_patients_patient_code ON patients (patient_code);

CREATE TABLE appointments (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	department_id INTEGER, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reason VARCHAR(300), 
	status VARCHAR(20) NOT NULL, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_appointments_patient_id ON appointments (patient_id);
CREATE INDEX ix_appointments_scheduled_at ON appointments (scheduled_at);
CREATE INDEX ix_appointments_doctor_id ON appointments (doctor_id);

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
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id), 
	FOREIGN KEY(assigned_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(reviewed_by) REFERENCES doctors (id)
);

CREATE INDEX ix_health_reports_assigned_doctor_id ON health_reports (assigned_doctor_id);
CREATE INDEX ix_health_reports_patient_id ON health_reports (patient_id);

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

CREATE INDEX ix_health_parameters_report_id ON health_parameters (report_id);
CREATE INDEX ix_health_parameters_normalized_name ON health_parameters (normalized_name);

CREATE TABLE prescriptions (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	report_id INTEGER, 
	prescription_date DATE NOT NULL, 
	clinical_indication VARCHAR(300), 
	status VARCHAR(25) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(report_id) REFERENCES health_reports (id)
);

CREATE INDEX ix_prescriptions_doctor_id ON prescriptions (doctor_id);
CREATE INDEX ix_prescriptions_patient_id ON prescriptions (patient_id);

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
