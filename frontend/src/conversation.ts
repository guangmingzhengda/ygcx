const LAST_KEY = 'ygcx:lastConversationId'
export const CONVERSATIONS_CHANGED = 'ygcx:conversations-changed'

export function getLastConversationId(): string | null {
  try {
    return sessionStorage.getItem(LAST_KEY)
  } catch {
    return null
  }
}

export function setLastConversationId(id: string) {
  try {
    sessionStorage.setItem(LAST_KEY, id)
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(CONVERSATIONS_CHANGED))
}

export function clearLastConversationId(id?: string) {
  try {
    if (!id || sessionStorage.getItem(LAST_KEY) === id) {
      sessionStorage.removeItem(LAST_KEY)
    }
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(CONVERSATIONS_CHANGED))
}

export function notifyConversationsChanged() {
  window.dispatchEvent(new Event(CONVERSATIONS_CHANGED))
}
