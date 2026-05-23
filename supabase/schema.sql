create extension if not exists pgcrypto;

create table if not exists public.restaurantes (
    id uuid primary key default gen_random_uuid(),
    crm_id text not null unique,
    unique_key text unique,
    key_google_maps_url text,
    key_nombre_direccion_comuna text,
    key_nombre_lat_lng text,
    nombre_restaurante text,
    nombre_normalizado text,
    rating numeric,
    cantidad_reviews integer,
    direccion text,
    telefono text,
    telefono_normalizado text,
    telefono_tipo text,
    whatsapp_disponible boolean default false,
    sitio_web text,
    categoria text,
    google_maps_url text,
    latitud numeric,
    longitud numeric,
    comuna text,
    region text,
    pais text,
    fuente text,
    fecha_extraccion timestamptz,
    fecha_carga timestamptz,
    calidad_dato text,
    es_restaurante_valido text,
    instagram_url text,
    instagram_usuario text,
    facebook_url text,
    tiktok_url text,
    tiene_redes text,
    calidad_redes text,
    esta_en_uber_eats text,
    url_uber_eats text,
    confianza_uber_eats text,
    esta_en_pedidosya text,
    url_pedidosya text,
    confianza_pedidosya text,
    esta_en_rappi text,
    en_rappi boolean,
    url_rappi text,
    confianza_rappi text,
    fecha_revision_rappi timestamptz,
    estado_revision_rappi text default 'No revisado',
    observacion_revision_rappi text,
    observaciones text,
    posible_cadena_franquicia text,
    grupo_cadena_franquicia text,
    posible_duplicado_entre_comunas text,
    grupo_duplicado text,
    tipo_negocio text,
    score_comercial numeric,
    nivel_comercial text,
    data_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.crm_estado (
    id uuid primary key default gen_random_uuid(),
    crm_id text not null unique,
    restaurante_id uuid references public.restaurantes(id) on delete set null,
    estado_crm text,
    fecha_ultimo_contacto timestamptz,
    canal_ultimo_contacto text,
    responsable text,
    observacion_crm text,
    proxima_accion text,
    fecha_proxima_accion timestamptz,
    fecha_ultimo_whatsapp timestamptz,
    mensaje_whatsapp_sugerido text,
    estado_whatsapp text,
    variante_mensaje text,
    mensaje_enviado text,
    fecha_envio_whatsapp timestamptz,
    respondio text,
    interesado text,
    reunion_agendada text,
    resultado_comercial text,
    resultado_seguimiento text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.historial_contactos (
    id uuid primary key default gen_random_uuid(),
    event_key text not null unique,
    crm_id text not null,
    restaurante_id uuid references public.restaurantes(id) on delete set null,
    fecha_hora timestamptz,
    restaurante text,
    comuna text,
    canal text,
    accion text,
    estado_crm_actual text,
    resultado_seguimiento_actual text,
    mensaje_enviado text,
    created_at timestamptz not null default now()
);

create table if not exists public.mensajes_whatsapp (
    id uuid primary key default gen_random_uuid(),
    codigo text not null unique,
    texto text not null,
    activo boolean not null default true,
    orden integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.logs_actualizaciones (
    id uuid primary key default gen_random_uuid(),
    fecha timestamptz,
    modo text,
    config_usada jsonb,
    comunas jsonb,
    encontrados integer default 0,
    insertados integer default 0,
    duplicados integer default 0,
    errores integer default 0,
    detenido_por_bloqueo boolean default false,
    notas text,
    created_at timestamptz not null default now()
);

create index if not exists idx_restaurantes_google_maps_url on public.restaurantes(google_maps_url);
create index if not exists idx_restaurantes_comuna on public.restaurantes(comuna);
create index if not exists idx_restaurantes_nivel on public.restaurantes(nivel_comercial);
create index if not exists idx_restaurantes_fecha_carga on public.restaurantes(fecha_carga);
create index if not exists idx_crm_estado_estado on public.crm_estado(estado_crm);
create index if not exists idx_crm_estado_resultado on public.crm_estado(resultado_seguimiento);
create index if not exists idx_historial_crm_id on public.historial_contactos(crm_id);
create index if not exists idx_historial_fecha on public.historial_contactos(fecha_hora);
create index if not exists idx_historial_canal on public.historial_contactos(canal);
create index if not exists idx_logs_fecha on public.logs_actualizaciones(fecha);
