#!/usr/bin/env python
from __future__ import annotations
from operator import index
import sys
import os
import contextlib
import datetime
import config
import sqlalchemy
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from itertools import product
from sqlalchemy import create_engine

@contextlib.contextmanager
def OpenClient(client:str) -> sqlalchemy.engine.base.Connection:
    '''
    sqlalchemy.engine.base.Engine
    Context manager for database
    '''
    conn = create_engine(f'sqlite:///{client}/planner.db').connect()
    yield conn
    conn.close()

@dataclass
class ClientData:

    client: str
    clientVariables: pd.DataFrame = field(init=False, repr=True)
    clientExpenses: pd.DataFrame = field(init=False, repr=True)
    clientAccounts: pd.DataFrame = field(init=False, repr=True)
    clientFuture: pd.DataFrame = field(init=False, repr=True)
    spendAdjustments: pd.DataFrame = field(init=False, repr=True)
    accountData: dict = field(init=False, repr=True)

    def __post_init__(self) -> None:
        self.Load()
    
    def Load(self) -> ClientData:

        with OpenClient(self.client) as conn:

            # Basic information
            self.clientVariables = pd.read_sql_table('variables', conn, index_col='Variable')
            self.clientExpenses = pd.read_sql_table('expenses', conn, index_col='Expense')
            self.clientAccounts = pd.read_sql_table('accounts', conn, index_col='Account')
            self.clientFuture = pd.read_sql_table('future', conn, index_col='Year')
            self.spendAdjustments = pd.read_sql_table('adjustments', conn, index_col='Year')
            
            # Annualized expenses
            try:
                self.annualExpenses = pd.read_sql_table('annualexpenses', conn, index_col='Year')
            except ValueError:
                self.BuildAnnualExpenses()
                self.annualExpenses.reset_index().to_sql('annualexpenses', conn, index=False)
            
            # Accounts info
            self.accountData = {}
            for accountName in self.clientAccounts.index:
                try:
                    currentAccount = pd.read_sql_table(accountName, conn, index_col='Year')
                except ValueError:
                    currentAccount = self.BuildPortfolio(accountName)
                    currentAccount.reset_index().to_sql(accountName, conn, index=False)
                self.accountData[accountName] = currentAccount

        return self

    def BuildPortfolio(self, accountName) -> pd.DataFrame:
        '''
        Build selected investment portfolio
        '''
        # Get investment type info
        lpf = self.clientAccounts
        build = (lpf.at[accountName, 'Build Rate'], lpf.at[accountName, 'Build Deviation'])
        withdraw = (lpf.at[accountName, 'Withdraw Rate'], lpf.at[accountName, 'Withdraw Deviation'])
        allRates = np.append(np.random.normal(build[0], build[1], self.WorkYears),
                             np.random.normal(withdraw[0], withdraw[1], self.RetireYears))
        endAge = lpf.at[accountName, 'End Age']
        contributionAmount = lpf.at[accountName, 'Contribution']
        contributionType = lpf.at[accountName, 'Contribution Type']

        # Build investment dataframe
        cols = ['Deposit', 'Withdraw', 'Balance', 'Rate']
        account = pd.DataFrame(columns=cols, index=self.years)
        account['Deposit'] = 0
        account['Withdraw'] = 0
        account['Balance'] = 0
        account['Rate'] = allRates
        account.at[account.index[0], 'Balance'] = lpf.at[accountName, 'Balance']
        if lpf.at[accountName, 'Account Type'] == 'Dividend':
            # Dividends are estimated as a percentage of portfolio balance
            account['Dividend'] = np.random.normal(contributionAmount, .001, len(self.years))

        # Build accounts
        for year in self.clientFuture.index[1:]:
            age = self.clientFuture.at[year, 'Age']
            account.at[year, 'Balance'] = account.at[year-1, 'Balance'] * (1+account.at[year, 'Rate'])
            if age < endAge:
                if contributionType == 'Balance':
                    account.at[year, 'Deposit'] = account.at[year-1, 'Balance'] * account.at[year, 'Dividend']
                elif contributionType == 'Salary':
                    account.at[year, 'Deposit'] = self.clientFuture.at[year, 'Income'] * contributionAmount
                else:
                    account.at[year, 'Deposit'] = contributionAmount
                account.at[year, 'Balance'] += account.at[year, 'Deposit']
        
        return account

    def BuildAnnualExpenses(self) -> ClientData:
        '''
        Get the estimate of expenses in a table for all years
        '''
        annualExpenses = pd.DataFrame({'Year': self.years})
        annualExpenses.set_index('Year', inplace=True)
        for expense in self.clientExpenses.index:
            annualExpenses[expense] = self.clientExpenses.at[expense, 'Value']
        if int(self.clientVariables.at['CPI Adjustment', 'Value']) == 1:
            for e in product(self.years[1:], self.clientExpenses.index):
                annualExpenses.at[e[0], e[1]] =  annualExpenses.at[e[0]-1, e[1]] * self.spendAdjustments.at[e[0], 'CPI']
                if e[1] == 'Medical':
                    annualExpenses.at[e[0], e[1]] *= self.spendAdjustments.at[e[0], 'CPI']
        annualExpenses['Non-Discretionary'] = annualExpenses.sum(axis=1)
        annualExpenses['Discretionary'] = self.spendAdjustments['Discretionary Spending'] * annualExpenses['Non-Discretionary']
        annualExpenses['Total'] = annualExpenses['Discretionary'] + annualExpenses['Non-Discretionary']
        self.clientFuture['Expenses'] = annualExpenses['Total']
        self.annualExpenses = annualExpenses

        return self

    def SocialSecurityIncome(self) -> ClientData:
        '''
        Handles social security income
        '''
        ssestimate = self.BaseSocialSecurityBenefit*12
        for year in self.years:
            if int(self.clientVariables.at['CPI Adjustment', 'Value']) == 1:
                ssestimate *= self.spendAdjustments.at[year, 'CPI']
            need = self.clientFuture.at[year, 'Expenses']
            if self.clientFuture.at[year, 'Age'] < self.FileAge:
                self.clientFuture.at[year, 'Social Security'] = 0
                self.clientFuture.at[year, 'need'] = self.clientFuture.at[year, 'Expenses'] - self.clientFuture.at[year, 'Income']
                continue
            self.clientFuture.at[year, 'Social Security'] = ssestimate
            self.clientFuture.at[year, 'need'] = need - ssestimate

        return self

    def AccountDrawdown(self) -> ClientData:
        '''
        Get additional income from specified account
        '''
        retireYears = self.clientFuture.query(f'Age >= {self.RetirementAge}').index
        drawdownOrder = self.clientAccounts.reset_index().set_index('Order').sort_index()['Account'].to_list()
        for e in product(retireYears, drawdownOrder):
            year = e[0]
            currentAge = self.clientFuture.at[year, 'Age']
            portfolio = self.accountData[e[1]] 
            accountType = self.clientAccounts.at[e[1], 'Account Type']
            need = self.clientFuture.at[year, 'need']
            rate = 1 + portfolio.at[year, 'Rate']
            if accountType == 'Dividend':
                withdrawal = portfolio.at[year-1, 'Balance'] * portfolio.at[year, 'Dividend']
                portfolio.at[year, 'Balance'] = portfolio.at[year-1, 'Balance'] * rate
            else:
                minWithdraw = 0
                if accountType == 'RMD' and currentAge >= config.RMD_AGE:
                    minWithdraw = portfolio.at[year-1, 'Balance']/config.RMDS[currentAge]
                withdrawal = min(max(need, minWithdraw), max(portfolio.at[year-1, 'Balance'], 0))
                portfolio.at[year, 'Withdraw'] = withdrawal
                portfolio.at[year, 'Balance'] = (portfolio.at[year-1, 'Balance'] - withdrawal) * rate
            self.clientFuture.at[year, e[1]] = withdrawal
            need -= withdrawal
            if need < 0:
                deposit = abs(need)
                self.accountData['Cash'].at[year, 'Deposit'] += deposit
                need = 0
            if e[1] == drawdownOrder[-1]:
                self.accountData['Cash'].at[year, 'Balance'] += self.accountData['Cash'].at[year, 'Deposit']
            self.clientFuture.at[year, 'need'] = need

        return self


    def SaveClient(self) -> ClientData:

        with OpenClient(self.client) as conn:
            self.clientVariables.reset_index().to_sql('variables', conn, index=False, if_exists='replace')
            self.clientExpenses.reset_index().to_sql('expenses', conn, index=False, if_exists='replace') 
            self.clientAccounts.reset_index().to_sql('accounts', conn, index=False, if_exists='replace')
            self.clientFuture.reset_index().to_sql('future', conn, index=False, if_exists='replace')
            for accountName in self.clientAccounts.index:
                portfolio = self.accountData[accountName]
                portfolio.reset_index().to_sql(accountName, conn, index=False, if_exists='replace')

        return self

    @property
    def years(self) -> pd.Series:
        return self.clientFuture.index

    @property
    def RetirementAge(self) -> int:
        return int(self.clientVariables.at['Retire age', 'Value'])

    @property
    def WorkYears(self) -> int:
        return len(self.clientFuture.query(f'Age < {self.RetirementAge}'))

    @property
    def RetireYears(self) -> int:
        return len(self.clientFuture.query(f'Age >= {self.RetirementAge}'))
    
    @property
    def FileAge(self) -> int:
        return int(self.clientVariables.at['File age', 'Value'])
    
    @property
    def BaseSocialSecurityBenefit(self) -> float:
        return float(self.clientVariables.at['PIA', 'Value'])

                        

def CreateClient(client: str) -> Self:
    '''
    Create given client
    '''
    
    # Client specific variables
    clientVariables = pd.DataFrame(config.variables)
    
    # Client expense estimates
    clientExpenses = pd.DataFrame(config.expenses)

    # Client accounts
    clientAccounts = pd.DataFrame(config.columns)
    
    # Client future starting with current
    values = config.variables['Value']
    currentYear = int(datetime.datetime.now().date().strftime('%Y'))
    finalYear = currentYear + (values[1]-values[0]) + values[3]
    years = list(range(currentYear, finalYear))
    clientAge = [values[0] + n for n in range(len(years))]
    clientFuture = pd.DataFrame({'Year': years, 'Age': clientAge})
    clientFuture['Income'] = [config.baseIncome if currentAge < values[1] else 0 for currentAge in clientAge]
    clientFuture['Expenses'] = 0
    
    clientAdjustments = pd.DataFrame({'Year': years, 'CPI': SetCpi(years), 'Discretionary Spending': [0 for _ in years]})

    # Create client planner database
    os.makedirs(client)
    with OpenClient(client) as conn:
        clientVariables.to_sql('variables', conn, index=False)
        clientExpenses.to_sql('expenses', conn, index=False) 
        clientAccounts.to_sql('accounts', conn, index=False)
        clientFuture.to_sql('future', conn, index=False)
        clientAdjustments.to_sql('adjustments', conn, index=False)

    return ClientData(client)

def SetCpi(years: pd.Series) -> pd.Series:
    '''
    Get CPI
    '''
    f = lambda x: abs(x)+1
    cpiEst = pd.Series(f(np.random.normal(config.CPI['mean'], config.CPI['deviation'], len(years))), index=years)
    cpiEst[years[0]] = 1
    return cpiEst

def FormatDataFrame(inframe: pd.DataFrame, viewer_format: dict) -> pd.DataFrame:
    '''
    Format a pandas dataframe given a dictionary
    '''
    df = inframe.reset_index()
    df = df.fillna(0)
    for key, value in viewer_format.items():
        if key in df.columns:
            df[key] = df[key].apply(value.format)
    return df

def main(args):

    from mytools import RichTableViewer
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()

    # Set client
    if len(args) > 1:
        client = args[1]
    else:
        client = console.input('[blue]No client given. What client would you like to work with? ')
        if len(client) == 0:
            console.print('[red]No client selected, exiting')
            return 0

    # Create client if none
    if os.path.isdir(client):
        database = ClientData(client)
    else:
        if console.input('[red]No such client. Create client? ').upper() in ('N', 'NO'):
            return 0
        config.baseIncome = float(Prompt.ask(f"What is {client}'s current salary?", default=str(config.baseIncome)))
        console.print(f'[blue]Creating client {client}')
        database = CreateClient(client)
    
    # Retirment income
    database.SocialSecurityIncome()
    database.AccountDrawdown()

    # Use rich to display table
    viewer_format = {
                    'Year': '{:.0f}',
                    'Age': '{:.0f}',
                    'Income': '${:,.2f}',
                    'Expenses': '${:,.2f}',
                    'Social Security': '${:,.2f}',
                    '401k': '${:,.2f}',
                    'Div': '${:,.2f}',
                    'Cash': '${:,.2f}'
                    }
    df = FormatDataFrame(database.clientFuture, viewer_format)
    data = [df.columns] + df.to_numpy().tolist()
    console.print(RichTableViewer(data, f"{client}'s Retirement Plan", 'cyan2'))

if __name__ == "__main__":
    sys.exit(main(sys.argv))
