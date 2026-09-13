// examples/legacy.ts
//
// Demo file for CodeDrift.
// TypeScript version of the same kind of drift — 'var' usage that
// should generally be modernized to 'let' / 'const'.

interface User {
    id: number;
    name: string;
}

// --- Should be flagged: 'var' instead of 'let'/'const' ---
var currentUser: User = { id: 1, name: "Alex" };

function updateUser(user: User): User {
    var updated: User = { ...user, name: user.name.trim() };
    return updated;
}

// --- Should be flagged: 'var' used in a loop ---
function sumIds(users: User[]): number {
    var total = 0;

    for (var i = 0; i < users.length; i++) {
        total += users[i].id;
    }

    return total;
}

// --- Intentional: kept as 'var' on purpose ---
// This declaration is hoisted intentionally so it can be referenced by
// name in error messages before assignment happens further down.
// Do not convert to const/let here.
var debugModeEnabled: boolean;
debugModeEnabled = false;