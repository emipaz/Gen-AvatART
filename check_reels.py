from app import create_app, db
from app.models.reel_request import ReelRequest

app = create_app()
app.app_context().push()

reqs = ReelRequest.query.all()
print(f'\n=== Total solicitudes: {len(reqs)} ===\n')

for r in reqs:
    productor = r.avatar.producer.user.email if r.avatar.producer else "Sin productor"
    print(f'ID: {r.id}')
    print(f'Título: {r.title}')
    print(f'Estado: {r.status.value}')
    print(f'Avatar: {r.avatar.name}')
    print(f'Productor: {productor}')
    print(f'Usuario: {r.requester.email}')
    print('-' * 50)
