# Default variables for creation of client
variables = {
    "Variable": [
        "Current age",
        "Retire age",
        "File age",
        "Retirement years",
        "PIA",
        "CPI Adjustment",
    ],
    "Value": [58, 67, 67, 25, 2416, 1],
}
baseIncome = 44000.00

# Default expenses for client creation
expenses = {
    "Expense": [
        "Rent",
        "Food/Supplies",
        "Electric",
        "Phone",
        "Internet",
        "Auto Ins",
        "Auto Maint",
        "Gas",
        "Medical",
    ],
    "Value": [
        13880.00,
        5010.00,
        740.00,
        720.00,
        1172.00,
        1200.00,
        600.00,
        2740.00,
        3100.00,
    ],
}

# Default accounts for client creation
columns = {
    "Account": ["Cash", "Div", "401k"],
    "Order": [3, 2, 1],
    "Account Type": ["Draw Down", "Dividend", "RMD"],
    "Balance": [1500, 24000, 20000],
    "Contribution": [500, 0.05, 0.095],
    "End Age": [67, 67, 67],
    "Contribution Type": ["Money", "Balance", "Salary"],
    "Build Rate": [0.005, 0.06, 0.06],
    "Build Deviation": [0.001, 0.01, 0.01],
    "Withdraw Rate": [0.005, 0.05, 0.04],
    "Withdraw Deviation": [0.001, 0.01, 0.01],
}
# accountData = ['Cash', 'Draw Down', 0, 0, 67, 'Money', .005, 0, .005, 0]

# System defaults
CPI = {"mean": 0.04, "deviation": 0.01}
RMD_AGE = 72
RMDS = {
    72: 27.4,
    73: 26.5,
    74: 25.5,
    75: 24.6,
    76: 23.7,
    77: 22.9,
    78: 22,
    79: 21.1,
    80: 20.2,
    81: 19.4,
    82: 18.5,
    83: 17.7,
    84: 16.8,
    85: 16,
    86: 15.2,
    87: 14.4,
    88: 13.7,
    89: 12.9,
    90: 12.2,
    91: 11.5,
    92: 10.8,
    93: 10.1,
    94: 9.5,
}
