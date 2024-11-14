#import flask mysqldb library

from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_mysqldb import MySQL
import MySQLdb.cursors, re
import mysql.connector

#import forecast library
import pandas as pd
from matplotlib import pyplot as plt
import numpy as np
import statsmodels.api as sm
from sklearn.metrics import mean_absolute_percentage_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from io import BytesIO

#initiate app and database
mydb= mysql.connector.connect(
    host='localhost',
    user='root',
    passwd='',
    database='adobe_database'
)

app = Flask(__name__)
app.secret_key = 'many random bytes'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'adobe_database'

mysql = MySQL(app)


#login
@app.route('/login/', methods=['GET', 'POST'])
def Login():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tabel_admin WHERE username = %s AND password = %s', (username, password,))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account['id_admin']
            session['username'] = account['username']
            flash('Anda berhasil masuk!')
            return redirect(url_for('Home'))
        else:
            flash("Username/Password salah!")
    return render_template('login.html')

#logout
@app.route('/logout')
def Logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('Login'))

#register
@app.route('/register', methods=['GET', 'POST'])
def Register():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tabel_admin WHERE username = %s', (username,))
        account = cursor.fetchone()
        if account:
            flash("Akun admin sudah ada!")
        elif not re.match(r'[A-Za-z0-9]+', username):
            flash("Username hanya boleh terdiri dari huruf dan angka!")
        elif not username or not password:
            flash("Mohon isi data di bawah")
        else:
            cursor.execute('INSERT INTO tabel_admin VALUES (NULL, %s, %s)', (username, password,))
            mysql.connection.commit()
            flash("Anda telah terdaftarkan")
    elif request.method == 'POST':
        flash("Mohon isi data di bawah")
    return render_template('register.html')

#homepage
@app.route('/home')
def Home():    
    return render_template('home.html')

@app.route('/profile')
def Profile():
    # Check if the user is logged in
    if 'loggedin' in session:
        # We need all the account info for the user so we can display it on the profile page
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM tabel_admin WHERE id_admin = %s', (session['id'],))
        account = cursor.fetchone()
        # Show the profile page with account info
        return render_template('profile.html', account=account)
    # User is not logged in redirect to login page
    flash("Fungsi ini hanya tersedia untuk admin, silahkan login dahulu.")
    return redirect(url_for('Login'))

@app.route('/updateprofile', methods=['POST','GET'])
def UpdateProfile():
    if 'loggedin' in session:
        if request.method == 'POST':
            username = session['username']
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            confirm_new_password = request.form['confirm_new_password']

            if new_password != confirm_new_password:
                flash("Password baru dan konfirmasi password tidak sama!", "error")
                return redirect(url_for('UpdateProfile'))
            
            cur = mysql.connection.cursor()
            cur.execute('SELECT password FROM tabel_admin WHERE username=%s and password=%s', (username, old_password))
            user=cur.fetchone()
            if user:
                cur.execute("""
                    UPDATE tabel_admin
                    SET password=%s
                    WHERE username=%s
                    """, (new_password, username))
                mysql.connection.commit()
            else:
                flash("Password lama tidak sesuai!")
                return redirect(url_for('UpdateProfile'))
            flash('Password berhasil diubah!')
        return render_template('updateprofile.html')
    return render_template('login.html')

#view data
@app.route('/view')
def View():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  * FROM tabel_pendapatan")
    data = cur.fetchall()
    cur.close()
    return render_template('view.html', pendapatan=data )

#insert data, must login
@app.route('/insert', methods = ['POST'])
def insert():
    if 'loggedin' in session:
        if request.method == "POST":
            flash("Data Inserted Successfully")
            periode = request.form['periode']
            pendapatan = request.form['pendapatan']
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO tabel_pendapatan (periode, pendapatan) VALUES (%s, %s)", (periode, pendapatan))
            mysql.connection.commit()
            return redirect(url_for('View'))
    flash("Fungsi ini hanya tersedia untuk admin, silahkan login dahulu.")
    return redirect(url_for('Login'))

#delete data, must login
@app.route('/delete/<string:id_data>', methods = ['GET'])
def delete(id_data):
    if 'loggedin' in session:
        flash("Record Has Been Deleted Successfully")
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM tabel_pendapatan WHERE id_pendapatan=%s", (id_data,))
        mysql.connection.commit()
        return redirect(url_for('View'))
    flash("Fungsi ini hanya tersedia untuk admin, silahkan login dahulu.")
    return redirect(url_for('Login'))

#update data, must login
@app.route('/update',methods=['POST','GET'])
def update():
    if 'loggedin' in session:
        if request.method == 'POST':
            id_data = request.form['id']
            periode = request.form['periode']
            pendapatan = request.form['pendapatan']
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE tabel_pendapatan
                SET periode=%s, pendapatan=%s
                WHERE id_pendapatan=%s
                """, (periode, pendapatan, id_data))
            flash("Data Updated Successfully")
            mysql.connection.commit()
        return redirect(url_for('View'))
    flash("Fungsi ini hanya tersedia untuk admin, silahkan login dahulu.")
    return redirect(url_for('Login'))

@app.route('/showforecast')
def ShowForecast():
    return render_template('forecast.html')

@app.route('/forecast.png')
def Forecast():
    #import data
    query = 'select * from tabel_pendapatan'
    df = pd.read_sql(query, con = mydb)
    df['periode']= pd.to_datetime(df['periode'])
    
    #plot original data
    df['quarter'] = df['periode'].dt.to_period('Q')
    df = df.drop(columns=['periode'])
    df['quarter_str'] = df['quarter'].astype(str)
    df = df.drop(columns=['quarter'])
    print(df)
    df.plot('quarter_str', 'pendapatan', title='Pendapatan Adobe per Tahun (dalam Miliar USD)', marker='o', xlabel='periode', ylabel='pendapatan', grid=True)

    #train and test data
    train = df.iloc[:16]
    test = df.iloc[16:]

    #forecasting
    model_additive = sm.tsa.ExponentialSmoothing(df['pendapatan'], trend='add', seasonal='add', seasonal_periods=4)
    tes_model_additive = model_additive.fit()
    print(tes_model_additive.summary())
    summary_html = tes_model_additive.summary().as_html()

    forecast_additive = tes_model_additive.forecast(steps=20)

    #MAPE
    MAPE_additive = mean_absolute_percentage_error(df.pendapatan, forecast_additive)


    #add forecasted years to dataframe
    additive = {'quarter_str': ['2024Q1', '2024Q2', '2024Q3', '2024Q4',
                                '2025Q1', '2025Q2', '2025Q3', '2025Q4',
                                '2026Q1', '2026Q2', '2026Q3', '2026Q4',
                                '2027Q1', '2027Q2', '2027Q3', '2027Q4',
                                '2028Q1', '2028Q2', '2028Q3', '2028Q4', ],
                    'Peramalan': forecast_additive}
    df_additive = pd.DataFrame(additive)
    df = pd.concat([df, df_additive], ignore_index=True)

    #plotting, additive
    plt.figure(figsize=(12,6))
    plt.title(f'Peramalan pendapatan Adobe Inc. menggunakan Metode Additive, MAPE = {MAPE_additive}')
    plt.margins(x=0.01, y=0.1)
    plt.grid(True)

    x = df['quarter_str']
    y1 = df['pendapatan']
    y2 = df['Peramalan']
    
    plt.plot(x, y1, label='Pendapatan', marker='o')
    plt.plot(x, y2, label='Peramalan', marker='o')
    plt.xticks(rotation=90)
    plt.legend(fontsize=20)

    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()
    return Response(img.getvalue(), mimetype='image/png')

if __name__ == "__main__":
    app.run(debug=True)
