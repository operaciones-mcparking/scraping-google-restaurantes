alter table public.restaurantes
add column if not exists en_rappi boolean,
add column if not exists url_rappi text,
add column if not exists fecha_revision_rappi timestamptz,
add column if not exists estado_revision_rappi text default 'No revisado',
add column if not exists observacion_revision_rappi text;

update public.restaurantes
set estado_revision_rappi = 'No revisado'
where estado_revision_rappi is null;

