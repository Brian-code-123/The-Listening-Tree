import { createServerClient } from "@supabase/ssr";

type CookieItem = {
  name: string;
  value: string;
  options?: Record<string, unknown>;
};

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY;

export const createClient = (cookieHeader: string | null | undefined) => {
  const setCookies: CookieItem[] = [];

  const supabase = createServerClient(supabaseUrl!, supabaseKey!, {
    cookies: {
      getAll() {
        if (!cookieHeader) {
          return [];
        }

        return cookieHeader
          .split(";")
          .map((item) => item.trim())
          .filter(Boolean)
          .map((item) => {
            const [name, ...rest] = item.split("=");
            return { name, value: rest.join("=") };
          });
      },
      setAll(cookiesToSet) {
        setCookies.push(...cookiesToSet);
      },
    },
  });

  return { supabase, setCookies };
};
