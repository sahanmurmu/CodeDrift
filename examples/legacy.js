// examples/legacy.js
//
// Demo file for CodeDrift.
// Contains a mix of outdated patterns (should be flagged) and one
// intentional pattern (should be skipped by the AI advisor).

// --- Should be flagged: 'var' instead of 'let'/'const' ---
var userName = "guest";
var isLoggedIn = false;

// --- Should be flagged: string concatenation instead of template literal ---
function greet(name) {
    return "Hello, " + name + "! Welcome back.";
}

// --- Should be flagged: anonymous function instead of arrow function ---
setTimeout(function () {
    console.log("Session check complete.");
}, 1000);

var scores = [10, 25, 30, 42];

// --- Should be flagged: anonymous callback in map ---
var doubledScores = scores.map(function (score) {
    return score * 2;
});

// --- Intentional: kept as 'var' on purpose for legacy browser support ---
// This function runs inside an old widget embed script that still needs
// to work in browsers without block scoping. Do not convert to let/const.
function legacyWidgetInit() {
    var containerId = "widget-root";
    return containerId;
}