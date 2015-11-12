from flask_wtf import Form
from wtforms import TextField, TextAreaField, ValidationError, SubmitField
from wtforms.validators import Required

class DropForm(Form):

    field1 = TextField('.onion domain', validators=[Required()])
    field2 = TextAreaField('Message', description="Copy paste encrypted text or enter your message plaintext and we'll encrypt it",
                       validators=[Required()])

    submit_button = SubmitField('Drop Mail')

class GoDrop(Form):
    submit_button = SubmitField('Drop')

class GetPack(Form):
    field1 = TextField('.onion domain', validators=[Required()])	
    submit_button = SubmitField('Pickup')

class GetAbout(Form):	
    submit_button = SubmitField('About')
