"""empty message

Revision ID: 65f05e470c64
Revises: ca2401fc7657
Create Date: 2024-08-22 19:11:21.003411

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65f05e470c64'
down_revision = 'ca2401fc7657'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('exercises', schema=None) as batch_op:
        batch_op.add_column(sa.Column('link', sa.String(length=300), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('exercises', schema=None) as batch_op:
        batch_op.drop_column('link')

    # ### end Alembic commands ###
