export const store = {
  get(key, fallback) {
    try {
      return JSON.parse(localStorage.getItem('tap.' + key)) ?? fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem('tap.' + key, JSON.stringify(value));
    } catch {
      /* storage unavailable: the preference just does not persist */
    }
  },
};
