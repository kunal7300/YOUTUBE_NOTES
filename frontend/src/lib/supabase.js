// src/lib/supabase.js — Supabase client singleton
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://uueporkqhbtcrjppausm.supabase.co'
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV1ZXBvcmtxaGJ0Y3JqcHBhdXNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgxMTE4MDIsImV4cCI6MjEwMzY4NzgwMn0.e94ZtIdxd14KxzRCHa7aDQdAwkAi4JLl8WwcDXmi--A'

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
