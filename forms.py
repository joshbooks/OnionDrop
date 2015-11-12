from flask_wtf import Form
from wtforms import TextField, TextAreaField, ValidationError, SubmitField
from wtforms.validators import Required

class DropForm(Form):

    field1 = TextField('.onion domain', validators=[Required()])
    field2 = TextAreaField('Message', description="You can enter plaintext and we'll encrypt it, or you can use <a href='https://github.com/joshbooks/OnionDrop/blob/master/enscrypt_noVerify.sh'>this script</a> and my fancy /key api to encrypt your message locally",
                       validators=[Required()])

    submit_button = SubmitField('Drop Mail')

class GoDrop(Form):
    submit_button = SubmitField('Drop')

class GetPack(Form):
    field1 = TextField('.onion domain', validators=[Required()])	
    submit_button = SubmitField('Pickup')

class GetAbout(Form):	
    submit_button = SubmitField('About')
