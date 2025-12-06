@echo off
:: Türkçe karakter sorununu aþmak için sayfa kodunu deðiþtiriyoruz
chcp 65001 > nul

:: Kullanýcý adýný otomatik bulur (%USERPROFILE%) ve Desktop (Masaüstü) dener
cd /d "%USERPROFILE%\OneDrive\Desktop\Python"

:: Eðer Desktop yemezse Masaüstü olarak dener (Türkçe karakter destekli)
if not exist "NewUser.py" cd /d "%USERPROFILE%\OneDrive\Masaüstü\Python"

echo Portfoy Asistani Baslatiliyor...
python -m streamlit run NewUser.py

pause