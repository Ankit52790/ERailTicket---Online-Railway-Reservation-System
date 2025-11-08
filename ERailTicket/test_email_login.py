import smtplib

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login("aankitkumar527909@gmail.com", "gsip bvtb ngxc qmew")
print("✅ Login successful")
