from flask import Flask, render_template, request, redirect, url_for, Response, flash, session
from flask_sqlalchemy import SQLAlchemy
import re
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import matplotlib.pyplot as plt
import statsmodels.api as sm
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error
from io import BytesIO

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
    periode = db.Column(db.Text(6), nullable = False)
    pendapatan = db.Column(db.Float, nullable = False)

class tabel_admin(db.Model, UserMixin):
    __tablename__ = 'tabel_admin'
    id_admin = db.Column(db.Integer, primary_key = True, autoincrement = True)
    username = db.Column(db.Text(45), unique=True, nullable = False)
    password = db.Column(db.Text(45), nullable = False)
    def get_id(self):
           return (self.id_admin)

# Initialize the database
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(id_admin):
    return tabel_admin.query.get(int(id_admin))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if tabel_admin.query.filter_by(username=username).first():
            flash('Username sudah ada!', 'danger')
            return redirect(url_for('register'))
        new_user = tabel_admin(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Berhasil terdaftarkan! Silahkan melakukan login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

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
            return redirect(url_for('home'))
        flash('Username/Password salah!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Berhasil logout!', 'success')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    if 'username' in session:
        return render_template('profile.html', username = session['username'])
    flash('Silahkan login terlebih dahulu!')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        username = session['username']
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_new_password = request.form['confirm_new_password']

        if new_password != confirm_new_password:
                flash("Password baru dan konfirmasi password tidak sama!", "error")
                return redirect(url_for('change_password'))
        
        user = tabel_admin.query.filter_by(username=username, password=current_password).first()        
        user.password = new_password
        db.session.commit()
        flash('Password berhasil diubah!')
        return redirect(url_for('home'))
    return render_template('change_password.html')

#homepage
@app.route('/home')
def home():    
    return render_template('home.html')

@app.route('/view')
def view():
    data = tabel_pendapatan.query.all()
    if current_user.is_authenticated:
        return render_template('view.html', data=data, header=session['username'])
    else:
        return render_template('view.html', data=data, header='Guest')

@app.route('/add', methods=['POST'])
@login_required
def add():
    data = tabel_pendapatan.query.all()
    periode = request.form['periode']
    pendapatan = request.form['pendapatan']
    if not re.match(r"^20\d{2}Q[1-4]$", periode):
        flash('Format periode salah! Silahkan gunakan format 20xxQx (contoh: 2019Q1)', 'danger')
        return redirect(url_for('view'))
    elif not re.match(r"\d*(\.\d+)?$", pendapatan):
        flash("Pendapatan harus terdiri dari angka!")
        return redirect(url_for('view'))
    else:
        if len(data) < 20:
            new_entry = tabel_pendapatan(periode=periode, pendapatan=pendapatan)
            db.session.add(new_entry)
            db.session.commit()
        else:
            flash("Jumlah data sudah mencapai maksimal")
    return redirect(url_for('view'))

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

@app.route('/delete/<int:id_pendapatan>', methods=['GET'])
@login_required
def delete(id_pendapatan):
    entry = tabel_pendapatan.query.get(id_pendapatan)
    if entry:
        db.session.delete(entry)
        db.session.commit()
    return redirect(url_for('view'))

@app.route('/forecast')
def forecast():
    data = tabel_pendapatan.query.all()
    if len(data) < 20:
        return "Hanya bisa melakukan peramalan jika terdapat 20 data dalam database"

    # Convert data to a Pandas DataFrame
    df = pd.DataFrame([(d.id_pendapatan, d.periode, d.pendapatan) for d in data], columns=['id_pendapatan', 'periode', 'pendapatan'])
    df.set_index('id_pendapatan', inplace=True)

    # Apply Exponential Smoothing for forecasting
    model = sm.tsa.ExponentialSmoothing(df['pendapatan'], trend='add', seasonal='add', seasonal_periods=4)
    fit=model.fit()
    print(fit.summary())
    forecast = fit.forecast(steps=20)  # Forecast the next 20 steps
    
    #MAPE
    MAPE = mean_absolute_percentage_error(df.pendapatan, forecast)

    # Plot the original data and forecast
    plt.figure(figsize=(10, 5))
    plt.grid(True)
    plt.plot(df.index, df['pendapatan'], label='Penjualan', marker='o')
    plt.plot(range(df.index[-1] + 1, df.index[-1] + 21), forecast, label='Peramalan', marker='o', linestyle='--')
    plt.title(f'Peramalan pendapatan Adobe Inc. menggunakan Metode Additive, MAPE = {MAPE}')
    plt.xlabel('Periode')
    plt.ylabel('Pendapatan')
    plt.legend()
    
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()
    return Response(img, mimetype='image/png')

@app.route('/forecast_summary')
def forecast_summary():
    data = tabel_pendapatan.query.all()

    # Convert data to a Pandas DataFrame
    df = pd.DataFrame([(d.id_pendapatan, d.periode, d.pendapatan) for d in data], columns=['id_pendapatan', 'periode', 'pendapatan'])
    df.set_index('id_pendapatan', inplace=True)

    # Apply Exponential Smoothing for forecasting
    model = sm.tsa.ExponentialSmoothing(df['pendapatan'], trend='add', seasonal='add', seasonal_periods=4)
    fit=model.fit()
    fit.summary()
    summary_html = fit.summary().as_html()
    if current_user.is_authenticated:
        return render_template('forecast_summary.html', summary=summary_html, header = session['username'])
    else:
        return render_template('forecast_summary.html', summary=summary_html, header = 'Guest')

if __name__ == '__main__':
    app.run(debug=True)
