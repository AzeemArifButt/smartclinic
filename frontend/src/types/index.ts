export interface Clinic {
  id: number;
  name: string;
  city: string;
  slug: string;
  whatsapp_number: string;
  wa_phone_number_id: string | null;
  opening_time: string;
  closing_time: string;
  plan: string;
}

export interface Doctor {
  id: number;
  name: string;
  specialty: string | null;
  is_active: boolean;
}

export interface QueueState {
  doctor_id: number;
  doctor_name: string;
  specialty: string | null;
  current_serving: number;
  total_issued_today: number;
}

export interface QueueStats {
  doctors: QueueState[];
}

export interface Token {
  id: number;
  token_number: number;
  patient_phone: string | null;
  token_type: "whatsapp" | "walkin";
  issued_at: string;
  doctor_id: number;
}

export interface Complaint {
  id: number;
  patient_phone: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface AuthUser {
  access_token: string;
  clinic_id: number;
  clinic_name: string;
  role: string;
}
