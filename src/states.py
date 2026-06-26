"""
IT: Costanti intere che rappresentano gli stati del ConversationHandler di
    python-telegram-bot. Sono definite come tupla `range(N)` per assegnare un
    intero univoco a ciascuno stato e ricalcolare automaticamente i valori se
    se ne aggiungono di nuovi. Per aggiungere un nuovo stato basta aggiungere
    il nome alla tupla e aumentare il valore di `range`.
EN: Integer constants representing the ConversationHandler states used by
    python-telegram-bot. Defined as a `range(N)` tuple so each state gets a
    unique integer that auto-renumbers when new states are added. To add a
    new state, append the name to the tuple and bump the `range` size.
"""
# =============================================================================
# CONVERSATION STATES
# =============================================================================
(
    MAIN_MENU,
    UPDATES_MENU,
    SYSTEM_MENU,
    SYSTEM_INFO,
    SYSTEM_CONFIRM,
    SYSTEM_RUNNING,
    SYSTEM_STATUS,
    CONTAINERS_LIST,
    CONTAINER_DETAIL,
    CONTAINER_CONFIRM,
    CONTAINER_RUNNING,
    ALL_CONFIRM,
    ALL_RUNNING,
    REBOOT_CONFIRM,
    REBOOT_RUNNING,
    SETTINGS_MENU,
    SETTINGS_INPUT,
    UPDATE_AVAILABLE,
) = range(18)
