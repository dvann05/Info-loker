import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
const supabaseKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  throw new Error(
    "Konfigurasi Supabase belum lengkap. Periksa file .env."
  );
}

export const supabase = createClient(
  supabaseUrl,
  supabaseKey
);
