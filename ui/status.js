const status = () => document.getElementById('action-status');

export function showStatus(message) {
  const element = status();
  element.textContent = message;
  element.hidden = false;
}

export function clearStatus(message) {
  const element = status();
  if (message && element.textContent !== message) return;
  element.textContent = '';
  element.hidden = true;
}
