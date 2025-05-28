#import libraries
from flask import Flask, render_template, request, redirect, url_for, Response, flash, session
from flask_sqlalchemy import SQLAlchemy
import re
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import matplotlib.pyplot as plt
import statsmodels.api as sm
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error
from io import BytesIO

#initiate app
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configure MySQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:''@localhost/adobe_database'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Define the database model
class tabel_pendapatan(db.Model):
    __tablename__ = 'tabel_pendapatan'
    id_pendapatan = db.Column(db.Integer, primary_key=True, autoincrement = True)
    periode = db.Column(db.Date, nullable = False)
    pendapatan = db.Column(db.Float, nullable = False)

class tabel_admin(db.Model, UserMixin):
    __tablename__ = 'tabel_admin'
    id_admin = db.Column(db.Integer, primary_key = True, autoincrement = True)
    username = db.Column(db.VARCHAR(45), unique=True, nullable = False)
    password = db.Column(db.VARCHAR(45), nullable = False)
    def get_id(self):
           return (self.id_admin)

# Initialize the database
with app.app_context():
    db.create_all()

#flask login manager
@login_manager.user_loader
def load_user(id_admin):
    return tabel_admin.query.get(int(id_admin))

#register admin
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if tabel_admin.query.filter_by(username=username).first():
            flash('Username sudah ada!', 'danger')
            return redirect(url_for('register'))
        if not re.match(r'^[A-Za-z0-9]{1,25}$', username):
            flash("Username tidak sesuai format yang diizinkan!")
            return redirect(url_for('register'))
        if not re.match(r'^.{8,}$', password):
            flash("Password tidak sesuai format yang diizinkan!")
            return redirect(url_for('register'))
        else:
            new_user = tabel_admin(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Berhasil terdaftarkan! Silahkan melakukan login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

#login admin
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        session['username'] = request.form['username']
        session['password'] = request.form['password']
        user = tabel_admin.query.filter_by(username=username, password=password).first()        
        if user:
            login_user(user)
            flash('Login berhasil!', 'success')
            return redirect(url_for('dashboard'))
        flash('Username/Password salah!', 'danger')
    return render_template('login.html')

#logout admin
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Berhasil logout!', 'success')
    return redirect(url_for('login'))

#profile admin
@app.route('/profile')
@login_required
def profile():
    if 'username' in session:
        return render_template('profile.html', username = session['username'])
    flash('Silahkan login terlebih dahulu!')
    return redirect(url_for('login'))

#change password admin
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        username = session['username']
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_new_password = request.form['confirm_new_password']

        #if confirm password doesnt match, error
        if new_password != confirm_new_password:
                flash("Password baru dan konfirmasi password tidak sama!", "error")
                return redirect(url_for('change_password'))
        
        if not re.match(r'^.{8,}$', new_password):
            flash("Password harus terdiri dari minimal 8 karakter!")
            return redirect(url_for('change_password'))
        
        user = tabel_admin.query.filter_by(username=username, password=current_password).first()        
        user.password = new_password
        db.session.commit()
        flash('Password berhasil diubah! Silahkan login kembali.')
        return redirect(url_for('logout'))
    return render_template('change_password.html')

#change username admin
@app.route('/change_username', methods=['GET', 'POST'])
@login_required
def change_username():
    username = session['username']
    if request.method == 'POST':
        new_username = request.form['new_username']
        if not re.match(r'^[A-Za-z0-9]{1,25}$', new_username):
            flash("Username tidak sesuai format yang diizinkan!")
            return redirect(url_for('change_username'))
        user = tabel_admin.query.filter_by(username=username).first()   
        if tabel_admin.query.filter_by(username=new_username).first():
            flash('Username sudah digunakan! Silahkan cobe untuk memasukkan username lain.', 'danger')
            return redirect(url_for('change_username'))   
        user.username = new_username
        db.session.commit()
        flash('Username berhasil diubah! Silahkan login kembali.')
        return redirect(url_for('logout'))
    return render_template('change_username.html', account=username)

#dashboard
@app.route('/dashboard')
def dashboard():    
    if current_user.is_authenticated:
        return render_template('dashboard.html', header=session['username'])
    else:
        return render_template('dashboard.html', header='Guest')

#view all data
@app.route('/view')
def view():
    data = tabel_pendapatan.query.order_by(tabel_pendapatan.periode.asc()).all()
    if current_user.is_authenticated:
        return render_template('view.html', data=data, header=session['username'])
    else:
        return render_template('view.html', data=data, header='Guest')

#add data
@app.route('/add', methods=['POST'])
@login_required
def add():
    data = tabel_pendapatan.query.all()
    periode = request.form['periode']
    pendapatan = request.form['pendapatan']
    #input format must be numbers, else = error
    if not re.match(r"\d*(\.\d+)?$", pendapatan):
        flash("Pendapatan harus terdiri dari angka!")
        return redirect(url_for('view'))
    else:
        #if amount of query < 20, input data. else = error
        if len(data) < 20:
            new_entry = tabel_pendapatan(periode=periode, pendapatan=pendapatan)
            db.session.add(new_entry)
            db.session.commit()
            flash('Data berhasil ditambahkan!')
        else:
            flash("Jumlah data sudah mencapai maksimal! Silahkan menghapus data penjualan yang ada jika diperlukan.")
    return redirect(url_for('view'))

#update data
@app.route('/update/<int:id_pendapatan>', methods=['POST'])
@login_required
def update(id_pendapatan):
    entry = tabel_pendapatan.query.get(id_pendapatan)
    pendapatan = request.form['pendapatan']
    entry.pendapatan = pendapatan
    if not re.match(r"\d*(\.\d+)?$", pendapatan):
        flash("Pendapatan harus terdiri dari angka!")
        return redirect(url_for('view'))
    db.session.commit()
    flash('Pendapatan berhasil diubah!')
    return redirect(url_for('view'))

#delete data
@app.route('/delete/<int:id_pendapatan>', methods=['GET'])
@login_required
def delete(id_pendapatan):
    entry = tabel_pendapatan.query.get(id_pendapatan)
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash('Data berhasil dihapus!')
    return redirect(url_for('view'))

#forecasting and plotting
@app.route('/forecast')
def forecast():
    #retrieve data
    data = tabel_pendapatan.query.order_by(tabel_pendapatan.periode.asc()).all()

    #convert to pandas dataframe
    df = pd.DataFrame([(d.periode, d.pendapatan) for d in data], columns=['Quarter', 'Pendapatan'])
    df['Quarter'] = pd.to_datetime(df['Quarter'])
    df = df.sort_values('Quarter')
    df['Quarter'] = df['Quarter'].dt.to_period('Q')  # Konversi ke Period

    #train and test data
    train_size = int(len(df) * 0.8)
    train, test = df.iloc[:train_size], df.iloc[train_size:]

    #train model
    model = sm.tsa.ExponentialSmoothing(
        train['Pendapatan'], 
        initial_level = 0.1, initial_trend = 0.1, initial_seasonal = 0.1,
        trend='add', 
        seasonal='add', 
        seasonal_periods=4
    )

    #forecast test data
    forecast = model.forecast(len(test))

    #MAPE calculation
    if (test['Pendapatan'] == 0).any():
        raise ValueError("Test data contains zero values, which will cause division error in MAPE.")
    MAPE = mean_absolute_percentage_error(test['Pendapatan'], forecast) * 100

    #forecast for the future period
    next_periods = 20
    last_period = test['Quarter'].iloc[-1]
    future_quarters = pd.period_range(start=last_period + 1, periods=next_periods, freq='Q')
    future_forecast = model.forecast(next_periods)

    #dataframe for forecasted values
    forecast_data = {'Quarter': future_quarters.astype(str), 'Peramalan': future_forecast}
    df_forecast = pd.DataFrame(forecast_data)

    #combine original data with forecasted value
    df['Quarter'] = df['Quarter'].astype(str)  # convert to string
    df['Peramalan'] = None
    df = pd.concat([df, df_forecast], ignore_index=True)

    #plotting
    plt.figure(figsize=(18, 10))
    plt.margins(x=0.01, y=0.05)
    plt.plot(df['Quarter'], df['Pendapatan'], label='Pendapatan Asli', marker='o')
    plt.plot(df['Quarter'], df['Peramalan'], label='Peramalan', linestyle='--', marker='o')
    plt.title(f'Peramalan Pendapatan menggunakan Additive Model, MAPE = {MAPE:.2f}%')
    plt.xlabel('Quarter')
    plt.ylabel('Pendapatan')
    plt.xticks(rotation=90)
    plt.grid(True)
    plt.legend(fontsize=20)

    #save image as plot
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()
    return Response(img, mimetype='image/png')


#show forecast plot and summaries
@app.route('/forecast_summary')
def forecast_summary():
    #retrieve data
    data = tabel_pendapatan.query.all()

    #error if database has <20 query
    if len(data) < 20:
        flash('Hanya bisa melakukan peramalan jika ada 20 data penjualan di database!')
        return redirect(url_for('view'))
    
    else:
        #convert to pandas dataframe
        pd.options.display.float_format = '{:.2f}'.format
        df = pd.DataFrame([(d.periode, d.pendapatan) for d in data], columns=['Quarter', 'Pendapatan'])
        df['Quarter'] = pd.to_datetime(df['Quarter'])
        df = df.sort_values('Quarter')
        df['Quarter'] = df['Quarter'].dt.to_period('Q')  # Konversi ke Period
        next_quarters = pd.PeriodIndex(df['Quarter'], freq='Q-DEC') + 20

        #train data
        train_size = int(len(df) * 0.8)
        train = df.iloc[:train_size]

        #train model
        model = sm.tsa.ExponentialSmoothing(
            train['Pendapatan'], 
            trend='add', 
            seasonal='add', 
            seasonal_periods=4
        )

        #forecast data
        forecast = model.forecast(20)
        df_forecast = pd.DataFrame({'Quarter (Peramalan)': next_quarters, 'Peramalan': forecast})

        #retrieve statsmodels.summary() data
        model.summary()
        summary_html = model.summary().as_html()

        if current_user.is_authenticated:
            return render_template('forecast_summary.html', summary=summary_html, header = session['username'], df=df.to_html(classes='table table-striped', index=False), df_forecast=df_forecast.to_html(classes='table table-striped', index=False))
        else:
            return render_template('forecast_summary.html', summary=summary_html, header = 'Guest', df=df.to_html(classes='table table-striped', index=False), df_forecast=df_forecast.to_html(classes='table table-striped', index=False))

if __name__ == '__main__':
    app.run
