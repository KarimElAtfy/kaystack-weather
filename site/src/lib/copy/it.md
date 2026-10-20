# Testi del sito (italiano)

Every Italian string of the site, in one place, for the owner to edit. Work notes are in English; the strings are the owner's to rewrite.

How to read this file:

- `chiave` is the key the code uses. Never rename a key without telling the engineer; changing the text is always safe.
- `dove` says where the string shows. `max` is the longest it may be (characters) before it breaks the layout at 320 px; "riga" means it may wrap freely.
- Words in braces, like `{ora}`, are filled in by the code. Keep them, move them as you like.
- Typography for every string: straight apostrophe ('), straight quotes ("), no long dashes, no three-dot character, no arrows, no emoji. Ranges are written "da 4 a 7" or "4-7" only where noted. Units have a space before them: "13 °C", "5 km". The code keeps number and unit on one line.
- Sentence case: capital only at the start of a sentence and for names.
- Long texts (the pages Come funziona, Fonti e licenze, Privacy, Quanto ci prendiamo) are under "Testi lunghi", one block per paragraph. They are drafts written to be rewritten.
- The build reads this file. It stops if the fixed words of a string (placeholders not counted) are longer than its `max`, if it holds a character from the typography line above, or if the code asks for a key that is not here.

Numbers, dates and times are formatted by the code in Italian (comma decimals, 24-hour clock, Europe/Rome). Weekday and month names come from the browser in Italian ("sabato", "ott").

## Sito e intestazione

| chiave                        | dove                                                                  | max  | testo                                                                                                                                    |
| ----------------------------- | --------------------------------------------------------------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `site.name`                   | intestazione, titolo della scheda                                     | 16   | Meteo                                                                                                                                    |
| `site.beta`                   | etichetta accanto al nome                                             | 6    | beta                                                                                                                                     |
| `site.beta_title`             | descrizione dell'etichetta beta per lettori di schermo e al passaggio | riga | Versione di prova: i dati possono mancare o essere sbagliati.                                                                            |
| `site.skip`                   | link per saltare al contenuto (visibile solo da tastiera)             | 30   | Vai al contenuto                                                                                                                         |
| `site.title_town`             | titolo della scheda del browser, pagina del paese                     | 60   | Meteo a {paese}: adesso, 48 ore, 10 giorni e radar                                                                                       |
| `site.title_home`             | titolo della scheda, pagina iniziale                                  | 60   | Meteo per Pedrengo e Sesto Calende                                                                                                       |
| `site.description`            | descrizione per i motori di ricerca                                   | 155  | Previsioni per Pedrengo e Sesto Calende corrette sulle stazioni ARPA vicine, con misure degli aeroporti e radar della Protezione Civile. |
| `switch.label`                | nome del selettore del paese, per lettori di schermo                  | riga | Scegli il paese                                                                                                                          |
| `switch.pedrengo`             | selettore del paese                                                   | 14   | Pedrengo                                                                                                                                 |
| `switch.sesto-calende`        | selettore del paese                                                   | 14   | Sesto Calende                                                                                                                            |
| `town.pedrengo`               | titolo della pagina                                                   | 30   | Pedrengo                                                                                                                                 |
| `town.sesto-calende`          | titolo della pagina                                                   | 30   | Sesto Calende                                                                                                                            |
| `town.province.pedrengo`      | accanto al titolo                                                     | 6    | BG                                                                                                                                       |
| `town.province.sesto-calende` | accanto al titolo                                                     | 6    | VA                                                                                                                                       |

## Pagina iniziale (selettore)

| chiave       | dove                                 | max  | testo                                                                                                                                                       |
| ------------ | ------------------------------------ | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `home.h1`    | titolo                               | 40   | Che tempo fa?                                                                                                                                               |
| `home.intro` | sotto il titolo                      | riga | Previsioni per due paesi della Lombardia, corrette ogni giorno sulla stazione ARPA più vicina. Il sito ricorda l'ultimo paese che hai scelto, senza cookie. |
| `home.ref`   | sotto il nome di ogni paese          | 60   | Stazione di riferimento: {stazione}, a {km}                                                                                                                 |
| `home.last`  | sopra il paese scelto l'ultima volta | 20   | Ultimo visto                                                                                                                                                |

## Navigazione della pagina del paese

| chiave      | dove                                                   | max  | testo                |
| ----------- | ------------------------------------------------------ | ---- | -------------------- |
| `nav.label` | nome della barra delle sezioni, per lettori di schermo | riga | Sezioni della pagina |
| `nav.now`   | barra delle sezioni                                    | 10   | Adesso               |
| `nav.h48`   | barra delle sezioni                                    | 10   | 48 ore               |
| `nav.d10`   | barra delle sezioni                                    | 10   | 10 giorni            |
| `nav.radar` | barra delle sezioni                                    | 10   | Radar                |

## Riga di fiducia (sotto il nome del paese)

| chiave             | dove                                                 | max  | testo                                                                  |
| ------------------ | ---------------------------------------------------- | ---- | ---------------------------------------------------------------------- |
| `trust.station`    | prima frase                                          | riga | Previsione fatta per la stazione ARPA di {stazione}, a {km} dal paese. |
| `trust.issued`     | seconda frase                                        | riga | Emessa alle {ora}, {fa}.                                               |
| `trust.issued_day` | seconda frase, se la previsione è di un altro giorno | riga | Emessa {giorno} alle {ora}, {fa}.                                      |
| `trust.why`        | link alla spiegazione                                | 30   | Perché una stazione?                                                   |

## Riga di stato (sotto la riga di fiducia)

One line under the station sentence, always the same height (two lines reserved), so nothing moves when the state changes. It shows one message, in this order of priority: offline, unreachable, missing, old, stale, normal. Every message stays within 62 characters with its values filled in. The hidden announcements are read once by screen readers when the state changes; ages are never in them.

| chiave               | dove                                                  | max | testo                                                          |
| -------------------- | ----------------------------------------------------- | --- | -------------------------------------------------------------- |
| `status.ok`          | riga di stato, normale (oggi)                         | 62  | Emessa alle {ora}, {fa}.                                       |
| `status.ok_day`      | riga di stato, normale (altro giorno)                 | 62  | Emessa {giorno} alle {ora}, {fa}.                              |
| `status.stale`       | riga di stato, previsione in ritardo (avviso)         | 62  | Emessa alle {ora}, {fa}: di solito si aggiorna ogni ora.       |
| `status.old`         | riga di stato, previsione di più di un giorno (grave) | 62  | Previsione vecchia: emessa {giorno} alle {ora}.                |
| `status.missing`     | riga di stato, nessuna previsione                     | 62  | Previsione non disponibile in questo momento.                  |
| `status.offline`     | riga di stato, dispositivo offline                    | 62  | Sei offline: dati scaricati alle {ora}.                        |
| `status.failed`      | riga di stato, letture fallite con dati vecchi        | 62  | Non riusciamo a scaricare i dati: gli ultimi sono delle {ora}. |
| `status.failed_none` | riga di stato, letture fallite senza dati             | 62  | Non riusciamo a scaricare i dati: riproviamo tra un minuto.    |
| `announce.stale`     | annuncio nascosto                                     | 40  | La previsione non è aggiornata.                                |
| `announce.old`       | annuncio nascosto                                     | 40  | La previsione è vecchia.                                       |
| `announce.offline`   | annuncio nascosto                                     | 40  | Sei offline.                                                   |
| `announce.failed`    | annuncio nascosto                                     | 40  | Non riusciamo a scaricare i dati.                              |
| `announce.back`      | annuncio nascosto, di nuovo in linea                  | 40  | Di nuovo in linea.                                             |

## Adesso

| chiave               | dove                                                                                  | max  | testo                                                           |
| -------------------- | ------------------------------------------------------------------------------------- | ---- | --------------------------------------------------------------- |
| `now.h2`             | titolo della sezione                                                                  | 20   | Adesso                                                          |
| `now.measured`       | etichetta accanto al titolo: distingue le misure dalle previsioni                     | 30   | misurato, non previsto                                          |
| `now.measured_short` | etichetta accanto al titolo Radar                                                     | 12   | osservato                                                       |
| `now.temp_label`     | nome della temperatura grande, per lettori di schermo                                 | riga | Temperatura misurata                                            |
| `airport.LIME`       | nome breve dell'aeroporto in Adesso; un codice sconosciuto usa il nome del bollettino | 20   | Orio al Serio                                                   |
| `airport.LIMC`       | nome breve dell'aeroporto in Adesso                                                   | 20   | Malpensa                                                        |
| `now.source_metar`   | sotto la temperatura                                                                  | riga | Aeroporto di {aeroporto}, a {km}. Bollettino delle {ora}, {fa}. |
| `now.wind`           | griglia dei valori                                                                    | 14   | Vento                                                           |
| `now.gust`           | griglia dei valori                                                                    | 14   | Raffiche                                                        |
| `now.humidity`       | griglia dei valori                                                                    | 14   | Umidità                                                         |
| `now.humidity_short` | sotto il valore dell'umidità                                                          | 12   | calcolata                                                       |
| `now.humidity_note`  | spiegazione dell'umidità (al passaggio e per lettori di schermo)                      | riga | Calcolata dalla temperatura e dal punto di rugiada.             |
| `now.dewpoint`       | griglia dei valori                                                                    | 18   | Punto di rugiada                                                |
| `now.visibility`     | griglia dei valori                                                                    | 14   | Visibilità                                                      |
| `now.sky`            | griglia dei valori: nuvole viste dall'aeroporto                                       | 14   | Nuvole                                                          |
| `now.weather_none`   | quando il bollettino non segnala fenomeni                                             | 30   | Nessun fenomeno segnalato                                       |
| `now.no_gust`        | raffiche assenti nel bollettino                                                       | 14   | nessuna                                                         |
| `now.rain_h3`        | titolo del blocco radar                                                               | 30   | Piove adesso?                                                   |
| `now.rain_none`      | il radar non vede pioggia sul paese né entro 10 km                                    | riga | Non piove, e non piove entro 10 km.                             |
| `now.rain_here_past` | piove sul paese, ma l'immagine è vecchia                                              | riga | Alle {ora} pioveva sul paese: pioggia {intensita}, {valore}.    |
| `now.rain_none_past` | non piove, ma l'immagine è vecchia                                                    | riga | Alle {ora} non pioveva sul paese.                               |
| `now.rain_none_near` | niente sul paese, ma qualcosa vicino                                                  | riga | Non piove sul paese.                                            |
| `now.rain_here`      | piove sul paese                                                                       | riga | Sì: pioggia {intensita}, {valore}.                              |
| `now.rain_5`         | entro 5 km                                                                            | riga | Entro 5 km: fino a {valore}.                                    |
| `now.rain_10`        | entro 10 km                                                                           | riga | Entro 10 km: fino a {valore}.                                   |
| `now.rain_5_none`    | entro 5 km, niente                                                                    | riga | Entro 5 km: niente.                                             |
| `now.rain_10_none`   | entro 10 km, niente                                                                   | riga | Entro 10 km: niente.                                            |
| `now.source_radar`   | sotto il blocco radar                                                                 | riga | Radar della Protezione Civile, immagine delle {ora}, {fa}.      |
| `now.to_radar`       | link alla sezione radar                                                               | 30   | Guarda il radar                                                 |
| `now.metar_raw`      | link per vedere il bollettino originale                                               | 40   | Bollettino METAR originale                                      |

## Prossime 48 ore

| chiave                  | dove                                                                 | max  | testo                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------- |
| `h48.h2`                | titolo della sezione                                                 | 24   | Prossime 48 ore                                                                                                                  |
| `h48.forecast`          | etichetta accanto al titolo                                          | 30   | previsto                                                                                                                         |
| `h48.meta`              | accanto al titolo                                                    | riga | Emessa alle {ora} per la stazione di {stazione}                                                                                  |
| `h48.summary_rain_most` | frase di sintesi: la maggior parte dei modelli dà pioggia            | riga | Pioggia per la maggior parte dei modelli {quando}.                                                                               |
| `h48.summary_rain_some` | frase di sintesi: solo alcuni modelli                                | riga | Qualche modello dà pioggia {quando}, la maggior parte no.                                                                        |
| `h48.summary_rain_none` | frase di sintesi: nessuna pioggia                                    | riga | Nessun modello dà pioggia nelle prossime 12 ore.                                                                                 |
| `h48.summary_from`      | parte della sintesi                                                  | 30   | dalle {ora}                                                                                                                      |
| `h48.summary_from_day`  | parte della sintesi, se è un altro giorno                            | 40   | {giorno} dalle {ora}                                                                                                             |
| `h48.summary_now`       | parte della sintesi, se è già in corso                               | 30   | già adesso                                                                                                                       |
| `h48.summary_temp`      | seconda frase di sintesi                                             | riga | Nelle prossime 48 ore la temperatura va da {min} a {max}.                                                                        |
| `h48.view_label`        | nome del selettore grafico o tabella                                 | riga | Come vedere le 48 ore                                                                                                            |
| `h48.view_chart`        | pulsante                                                             | 12   | Grafico                                                                                                                          |
| `h48.view_table`        | pulsante                                                             | 12   | Tabella                                                                                                                          |
| `h48.panel_temp`        | titolo del pannello                                                  | 40   | Temperatura (°C)                                                                                                                 |
| `h48.panel_temp_note`   | sotto il titolo del pannello                                         | riga | Corretta sulla stazione. La fascia è l'intervallo tra i modelli.                                                                 |
| `h48.panel_rain`        | titolo del pannello                                                  | 40   | Pioggia: quanti modelli la danno                                                                                                 |
| `h48.panel_rain_note`   | sotto il titolo del pannello                                         | riga | Modelli con almeno 0,2 mm in un'ora. Non è una probabilità.                                                                      |
| `h48.panel_wind`        | titolo del pannello                                                  | 40   | Vento (km/h)                                                                                                                     |
| `h48.panel_wind_note`   | sotto il titolo del pannello                                         | riga | Media dei modelli, senza correzione.                                                                                             |
| `h48.legend_mean`       | legenda del pannello temperatura                                     | 24   | temperatura corretta                                                                                                             |
| `h48.legend_range`      | legenda del pannello temperatura                                     | 30   | intervallo tra i modelli                                                                                                         |
| `h48.legend_rain`       | legenda del pannello pioggia                                         | 24   | modelli con pioggia                                                                                                              |
| `h48.legend_wind`       | legenda del pannello vento                                           | 16   | vento medio                                                                                                                      |
| `h48.legend_gust`       | legenda del pannello vento                                           | 16   | raffiche                                                                                                                         |
| `h48.axis_all`          | asse del pannello pioggia, in alto                                   | 8    | tutti                                                                                                                            |
| `h48.axis_half`         | asse del pannello pioggia, a metà                                    | 8    | metà                                                                                                                             |
| `h48.axis_none`         | asse del pannello pioggia, in basso                                  | 8    | nessuno                                                                                                                          |
| `h48.now_marker`        | segno verticale dell'ora attuale                                     | 8    | ora                                                                                                                              |
| `h48.dst_marker`        | segno del cambio d'ora nel grafico                                   | 20   | ora solare                                                                                                                       |
| `h48.dst_note`          | nota sopra il giorno del cambio d'ora                                | riga | Questa notte torna l'ora solare: alle 3 si torna alle 2, e le ore dalle 2 alle 3 si ripetono.                                    |
| `h48.readout_label`     | nome del riquadro dei valori dell'ora scelta                         | riga | Valori dell'ora scelta                                                                                                           |
| `h48.readout_temp`      | riquadro dei valori, dopo la temperatura                             | riga | modelli da {min} a {max}                                                                                                         |
| `h48.cell_range`        | tabella, sotto la temperatura                                        | 14   | da {min} a {max}                                                                                                                 |
| `h48.readout_rain`      | riquadro dei valori                                                  | riga | Pioggia: {modelli}, {mm}                                                                                                         |
| `h48.readout_mm`        | riquadro dei valori, dopo i modelli                                  | 30   | in media {mm}                                                                                                                    |
| `h48.readout_wind`      | riquadro dei valori                                                  | riga | Vento {v} da {dir}, raffiche {g}                                                                                                 |
| `h48.readout_cloud`     | riquadro dei valori                                                  | riga | Nuvole {pct}                                                                                                                     |
| `h48.range_label`       | nome del cursore sotto il grafico, per tastiera e lettori di schermo | 24   | Ora del grafico                                                                                                                  |
| `h48.chart_help`        | aiuto sotto il grafico e il cursore                                  | riga | Tocca o trascina sul grafico per vedere un'ora. Da tastiera usa il cursore qui sopra.                                            |
| `h48.chart_aria`        | descrizione del grafico per lettori di schermo                       | riga | Grafico delle prossime 48 ore. Temperatura da {min} a {max}. {pioggia} I valori sono anche nella tabella.                        |
| `h48.footnote`          | sotto il grafico e la tabella                                        | riga | Solo la temperatura è corretta sulla stazione. Vento, raffiche, nuvole e quantità di pioggia sono la media semplice dei modelli. |
| `h48.models_note`       | sotto il grafico e la tabella                                        | riga | Modelli usati: {m} fino a {ora1}, poi meno, perché alcuni non arrivano così lontano.                                             |
| `h48.table_caption`     | titolo della tabella (per lettori di schermo)                        | riga | Previsione ora per ora per le prossime 48 ore                                                                                    |
| `h48.col_time`          | intestazione della tabella                                           | 10   | Ora                                                                                                                              |
| `h48.col_sky`           | intestazione della tabella                                           | 10   | Cielo                                                                                                                            |
| `h48.col_temp`          | intestazione della tabella                                           | 8    | Temp.                                                                                                                            |
| `h48.col_temp_sub`      | sotto l'intestazione                                                 | 14   | tra i modelli                                                                                                                    |
| `h48.col_rain`          | intestazione della tabella                                           | 12   | Pioggia                                                                                                                          |
| `h48.col_rain_sub`      | sotto l'intestazione                                                 | 12   | modelli, mm                                                                                                                      |
| `h48.col_wind`          | intestazione della tabella                                           | 12   | Vento                                                                                                                            |
| `h48.col_wind_sub`      | sotto l'intestazione                                                 | 12   | km/h                                                                                                                             |
| `h48.col_cloud`         | sotto l'intestazione Cielo                                           | 10   | nuvole                                                                                                                           |
| `h48.cell_gust`         | cella del vento                                                      | 16   | raffiche {g}                                                                                                                     |
| `h48.cell_dst_before`   | sotto la prima delle due 02:00 del giorno del cambio                 | 16   | ora legale                                                                                                                       |
| `h48.cell_dst`          | accanto all'ora ripetuta nel giorno del cambio                       | 16   | ora solare                                                                                                                       |

## 10 giorni

| chiave                   | dove                                               | max  | testo                                                                                                                                             |
| ------------------------ | -------------------------------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `d10.h2`                 | titolo della sezione                               | 24   | Prossimi 10 giorni                                                                                                                                |
| `d10.caption`            | titolo della tabella (per lettori di schermo)      | riga | Minima, massima e pioggia per i prossimi 10 giorni                                                                                                |
| `d10.col_day`            | intestazione                                       | 10   | Giorno                                                                                                                                            |
| `d10.col_sky`            | intestazione                                       | 10   | Cielo                                                                                                                                             |
| `d10.col_min`            | intestazione                                       | 8    | Minima                                                                                                                                            |
| `d10.col_max`            | intestazione, nome completo per lettori di schermo | 8    | Massima                                                                                                                                           |
| `d10.col_min_short`      | intestazione visibile                              | 4    | min                                                                                                                                               |
| `d10.col_max_short`      | intestazione visibile                              | 4    | max                                                                                                                                               |
| `d10.col_rain`           | intestazione                                       | 12   | Pioggia                                                                                                                                           |
| `d10.col_rain_sub`       | sotto l'intestazione                               | 30   | modelli con almeno 1 mm                                                                                                                           |
| `d10.today`              | nome del giorno                                    | 10   | Oggi                                                                                                                                              |
| `d10.tomorrow`           | nome del giorno                                    | 10   | Domani                                                                                                                                            |
| `d10.cell_range`         | testo per lettori di schermo nella riga del giorno | riga | minima {min} (modelli da {minlo} a {minhi}), massima {max} (modelli da {maxlo} a {maxhi})                                                         |
| `d10.less_reliable_h3`   | separatore prima dei giorni 8-10                   | 40   | Da qui in poi meno affidabile                                                                                                                     |
| `d10.less_reliable_note` | sotto il separatore                                | riga | Arrivano così lontano solo {m} modelli, e la correzione è quella del giorno 7.                                                                    |
| `d10.legend_bar`         | legenda della barra                                | riga | La barra va dalla minima alla massima. Le estremità più chiare sono l'intervallo tra i modelli.                                                   |
| `d10.footnote`           | sotto la tabella                                   | riga | Minima e massima sono corrette sulla stazione di {stazione}. La pioggia conta quanti modelli danno almeno 1 mm nel giorno: non è una probabilità. |

## Radar

| chiave                    | dove                                                                  | max  | testo                                                                 |
| ------------------------- | --------------------------------------------------------------------- | ---- | --------------------------------------------------------------------- |
| `radar.h2`                | titolo della sezione                                                  | 20   | Radar                                                                 |
| `radar.sub`               | sotto il titolo                                                       | riga | L'ultima ora osservata, un'immagine ogni 5 minuti.                    |
| `radar.map_label`         | descrizione della mappa per lettori di schermo                        | riga | Mappa del radar intorno a {paese}, immagine delle {ora}. {sintesi}    |
| `radar.observed`          | etichetta sull'immagine                                               | 12   | osservato                                                             |
| `radar.forecast`          | etichetta sull'immagine, dalla v1.1                                   | 12   | previsto                                                              |
| `radar.play`              | pulsante                                                              | 10   | Avvia                                                                 |
| `radar.pause`             | pulsante                                                              | 10   | Ferma                                                                 |
| `radar.latest`            | pulsante                                                              | 12   | Ultima                                                                |
| `radar.slider`            | nome del cursore del tempo                                            | riga | Ora dell'immagine                                                     |
| `radar.frame_missing`     | nel cursore e nella frase, quando manca un fotogramma                 | 30   | immagine mancante                                                     |
| `radar.frame_missing_box` | riquadro sopra la mappa velata, quando manca un fotogramma            | riga | Manca l'immagine delle {ora}.                                         |
| `radar.loading`           | riquadro sopra la mappa velata, finché le immagini non sono disegnate | 30   | Carico le immagini                                                    |
| `radar.legend_title`      | titolo della legenda                                                  | 30   | Pioggia (mm/h)                                                        |
| `radar.legend_nodata`     | legenda                                                               | 16   | nessun dato                                                           |
| `radar.class.1`           | legenda, prima classe                                                 | 14   | molto debole                                                          |
| `radar.class.2`           | legenda                                                               | 14   | debole                                                                |
| `radar.class.3`           | legenda                                                               | 14   | moderata                                                              |
| `radar.class.4`           | legenda                                                               | 14   | forte                                                                 |
| `radar.class.5`           | legenda                                                               | 14   | molto forte                                                           |
| `radar.class.6`           | legenda, ultima classe                                                | 14   | nubifragio                                                            |
| `radar.rings`             | legenda degli anelli                                                  | riga | Anelli a 10, 25 e 50 km dal paese.                                    |
| `radar.over`              | legenda, ultima classe                                                | 10   | oltre {v}                                                             |
| `radar.summary`           | sotto la mappa, cambia con l'immagine                                 | riga | Alle {ora}: {qui} {vicino}                                            |
| `radar.sum_here`          | parte della frase sotto la mappa                                      | riga | sul paese piove ({classe}).                                           |
| `radar.sum_here_none`     | parte della frase sotto la mappa                                      | riga | sul paese non piove.                                                  |
| `radar.sum_near`          | parte della frase sotto la mappa                                      | riga | Entro 10 km la pioggia più forte è {classe}.                          |
| `radar.sum_near_none`     | parte della frase sotto la mappa                                      | riga | Entro 10 km non piove.                                                |
| `radar.probe_hint`        | sotto la legenda                                                      | riga | Tocca la mappa per leggere la pioggia in un punto.                    |
| `radar.probe`             | sotto la mappa, dopo aver toccato un punto                            | riga | A {km} a {dir} di {paese}: {valore}.                                  |
| `radar.probe_town`        | sotto la mappa, punto sul paese                                       | riga | Su {paese}: {valore}.                                                 |
| `radar.probe_dry`         | valore del punto toccato                                              | 16   | non piove                                                             |
| `radar.credit`            | sotto l'immagine, sempre visibile                                     | riga | Radar: Dipartimento della Protezione Civile (Radar-DPC), CC BY-SA 4.0 |
| `radar.basemap_credit`    | sotto l'immagine                                                      | riga | Mappa: Natural Earth.                                                 |
| `radar.unavailable`       | al posto della mappa                                                  | riga | Radar non disponibile.                                                |
| `radar.unavailable_since` | sotto                                                                 | riga | L'ultima immagine arrivata è delle {ora}, {fa}.                       |
| `radar.stale`             | sopra la mappa, se le immagini sono vecchie                           | riga | Il radar non si aggiorna dalle {ora}: le immagini sono di {fa}.       |

## Stati: caricamento, dati vecchi, dati mancanti, fuori linea

| chiave                     | dove                                               | max  | testo                                                                                               |
| -------------------------- | -------------------------------------------------- | ---- | --------------------------------------------------------------------------------------------------- |
| `state.loading`            | al posto dei valori mentre arrivano                | 30   | Carico i dati                                                                                       |
| `state.nodata`             | al posto di un singolo valore assente              | 6    | n.d.                                                                                                |
| `state.nodata_title`       | spiegazione di n.d.                                | riga | Dato non disponibile                                                                                |
| `state.stale_tag`          | etichetta accanto a un valore vecchio              | 16   | non aggiornato                                                                                      |
| `state.metar_stale`        | Adesso, bollettino vecchio                         | riga | L'ultimo bollettino dell'aeroporto è delle {ora}, {fa}: i valori qui sotto non dicono com'è adesso. |
| `state.metar_expired`      | Adesso, bollettino troppo vecchio per mostrarlo    | riga | Nessun bollettino dell'aeroporto dalle {ora}. Non mostriamo valori così vecchi.                     |
| `state.metar_missing`      | Adesso, nessun bollettino                          | riga | I dati dell'aeroporto non sono disponibili.                                                         |
| `state.radar_missing`      | Adesso, nessun dato radar                          | riga | Il radar non è disponibile, quindi non sappiamo se piove adesso.                                    |
| `state.radar_nodata_here`  | Adesso, il radar non vede la zona del paese        | riga | Il radar non copre la zona del paese in questa immagine.                                            |
| `state.forecast_stale`     | avviso in alto                                     | riga | La previsione è delle {ora}, {fa}. Di solito si aggiorna ogni ora.                                  |
| `state.forecast_old`       | avviso in alto, previsione di più di un giorno     | riga | La previsione è vecchia: emessa {giorno} alle {ora}. Le ore già passate non sono mostrate.          |
| `state.forecast_missing`   | al posto di 48 ore e 10 giorni                     | riga | La previsione non è disponibile in questo momento.                                                  |
| `state.partial_hours`      | sotto il grafico, se mancano ore                   | riga | Mancano alcune ore: dove non c'è un modello corretto non mostriamo niente.                          |
| `state.offline`            | avviso in alto                                     | riga | Sei offline. Vedi i dati scaricati alle {ora}.                                                      |
| `state.fetch_failed`       | avviso in alto                                     | riga | Non riusciamo a scaricare i dati. Riproviamo tra un minuto.                                         |
| `state.fetch_failed_since` | seconda frase dell'avviso                          | riga | Gli ultimi dati sono delle {ora}.                                                                   |
| `state.cause_openmeteo`    | seconda frase dell'avviso sulla previsione vecchia | riga | Open-Meteo, da cui arrivano i modelli, non risponde dalle {ora}.                                    |
| `state.down.radar`         | avviso in alto, radar fermo                        | riga | Il radar della Protezione Civile non risponde dalle {ora}: le immagini non si aggiornano.           |
| `state.down.open-meteo`    | avviso in alto, modelli fermi                      | riga | Open-Meteo, da cui arrivano i modelli, non risponde dalle {ora}: la previsione non si aggiorna.     |
| `state.down.metar`         | avviso in alto, bollettini fermi                   | riga | I bollettini degli aeroporti non arrivano dalle {ora}.                                              |
| `state.noscript`           | se JavaScript è spento                             | riga | Per vedere i dati serve JavaScript: il sito li scarica dal nostro archivio ogni minuto.             |
| `state.refreshed`          | piè di pagina                                      | riga | Dati controllati alle {ora}.                                                                        |

## Piè di pagina e stato delle fonti

| chiave                  | dove                                                             | max  | testo                                                                                                                                                                                            |
| ----------------------- | ---------------------------------------------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `footer.status_h2`      | titolo apribile                                                  | 30   | Stato delle fonti                                                                                                                                                                                |
| `footer.status_ok`      | accanto a una fonte aggiornata                                   | 16   | aggiornata                                                                                                                                                                                       |
| `footer.status_late`    | accanto a una fonte in ritardo                                   | 16   | in ritardo                                                                                                                                                                                       |
| `footer.status_down`    | accanto a una fonte ferma                                        | 16   | ferma                                                                                                                                                                                            |
| `footer.status_row`     | riga di una fonte                                                | riga | Dati delle {ora}, {fa}                                                                                                                                                                           |
| `footer.src.metar`      | nome della fonte                                                 | 40   | Bollettini METAR degli aeroporti                                                                                                                                                                 |
| `footer.src.radar`      | nome della fonte                                                 | 40   | Radar della Protezione Civile                                                                                                                                                                    |
| `footer.src.open-meteo` | nome della fonte                                                 | 40   | Modelli meteorologici (Open-Meteo)                                                                                                                                                               |
| `footer.src.arpa`       | nome della fonte                                                 | 40   | Stazioni ARPA Lombardia                                                                                                                                                                          |
| `footer.src.arpa_note`  | sotto ARPA                                                       | riga | Arrivano con 3-9 ore di ritardo: servono a correggere e verificare, non per Adesso.                                                                                                              |
| `footer.credits`        | crediti, sempre visibili                                         | riga | Dati dei modelli: Open-Meteo.com, CC BY 4.0. Radar: Dipartimento della Protezione Civile (Radar-DPC), CC BY-SA 4.0. Osservazioni: METAR, NOAA Aviation Weather Center. Stazioni: ARPA Lombardia. |
| `footer.how`            | link                                                             | 20   | Come funziona                                                                                                                                                                                    |
| `footer.sources`        | link                                                             | 20   | Fonti e licenze                                                                                                                                                                                  |
| `footer.score`          | link                                                             | 24   | Quanto ci prendiamo                                                                                                                                                                              |
| `footer.score_soon`     | accanto al link                                                  | 16   | da fine novembre                                                                                                                                                                                 |
| `footer.privacy`        | link                                                             | 12   | Privacy                                                                                                                                                                                          |
| `footer.code`           | link al codice                                                   | 30   | Codice sorgente                                                                                                                                                                                  |
| `footer.nav_label`      | nome della navigazione del piè di pagina, per lettori di schermo | riga | Pagine del sito                                                                                                                                                                                  |
| `footer.beta`           | ultima riga                                                      | riga | Versione beta. I dati possono mancare o essere sbagliati: non usarli per decisioni di sicurezza.                                                                                                 |

## Unità, tempi, direzioni

| chiave           | dove                                         | max | testo                 |
| ---------------- | -------------------------------------------- | --- | --------------------- |
| `unit.c`         | dopo una temperatura                         | 3   | °C                    |
| `unit.kmh`       | dopo una velocità                            | 5   | km/h                  |
| `unit.mm`        | dopo una quantità di pioggia                 | 3   | mm                    |
| `unit.mmh`       | dopo un'intensità di pioggia                 | 5   | mm/h                  |
| `unit.km`        | dopo una distanza                            | 3   | km                    |
| `unit.m`         | dopo una distanza                            | 2   | m                     |
| `unit.pct`       | dopo una percentuale                         | 1   | %                     |
| `vis.max`        | visibilità di 10 km o più                    | 16  | oltre 10 km           |
| `time.just_now`  | età sotto un minuto                          | 12  | adesso                |
| `time.min_ago`   | età in minuti                                | 14  | {n} min fa            |
| `time.hour_ago`  | età di un'ora esatta                         | 14  | 1 ora fa              |
| `time.hours_ago` | età in ore, da 3 ore in su                   | 14  | {n} ore fa            |
| `time.hm_ago`    | età in ore e minuti, sotto le 3 ore          | 20  | {h} h {m} min fa      |
| `time.yesterday` | giorno                                       | 10  | ieri                  |
| `time.at`        | ora del giorno                               | 12  | alle {ora}            |
| `time.hour_word` | nella tabella oraria, per lettori di schermo | 10  | ore {ora}             |
| `models.one`     | conteggio dei modelli                        | 20  | 1 modello su {m}      |
| `models.many`    | conteggio dei modelli                        | 20  | {n} modelli su {m}    |
| `models.none`    | conteggio dei modelli                        | 24  | nessun modello su {m} |
| `models.short`   | conteggio breve, in tabella                  | 8   | {n}/{m}               |
| `wind.calm`      | vento sotto 2 km/h                           | 10  | calma                 |
| `wind.variable`  | direzione variabile                          | 12  | variabile             |
| `wind.from`      | direzione lunga                              | 16  | da {dir}              |
| `dir.N`          | direzione breve                              | 2   | N                     |
| `dir.NE`         | direzione breve                              | 2   | NE                    |
| `dir.E`          | direzione breve                              | 2   | E                     |
| `dir.SE`         | direzione breve                              | 2   | SE                    |
| `dir.S`          | direzione breve                              | 2   | S                     |
| `dir.SO`         | direzione breve                              | 2   | SO                    |
| `dir.O`          | direzione breve                              | 2   | O                     |
| `dir.NO`         | direzione breve                              | 2   | NO                    |
| `dirlong.N`      | direzione lunga                              | 12  | nord                  |
| `dirlong.NE`     | direzione lunga                              | 12  | nord-est              |
| `dirlong.E`      | direzione lunga                              | 12  | est                   |
| `dirlong.SE`     | direzione lunga                              | 12  | sud-est               |
| `dirlong.S`      | direzione lunga                              | 12  | sud                   |
| `dirlong.SO`     | direzione lunga                              | 12  | sud-ovest             |
| `dirlong.O`      | direzione lunga                              | 12  | ovest                 |
| `dirlong.NO`     | direzione lunga                              | 12  | nord-ovest            |

## Simboli del cielo (testo alternativo)

| chiave            | dove                       | max  | testo                        |
| ----------------- | -------------------------- | ---- | ---------------------------- |
| `sky.clear_day`   | simbolo                    | 30   | Sereno                       |
| `sky.clear_night` | simbolo                    | 30   | Sereno                       |
| `sky.few_day`     | simbolo                    | 30   | Poco nuvoloso                |
| `sky.few_night`   | simbolo                    | 30   | Poco nuvoloso                |
| `sky.cloudy`      | simbolo                    | 30   | Nuvoloso                     |
| `sky.overcast`    | simbolo                    | 30   | Coperto                      |
| `sky.rain_maybe`  | simbolo                    | 30   | Pioggia possibile            |
| `sky.rain_1`      | simbolo                    | 30   | Pioggia debole               |
| `sky.rain_2`      | simbolo                    | 30   | Pioggia                      |
| `sky.rain_3`      | simbolo                    | 30   | Pioggia forte                |
| `sky.fog`         | simbolo, solo in Adesso    | 30   | Nebbia                       |
| `sky.thunder`     | simbolo, solo in Adesso    | 30   | Temporale                    |
| `sky.snow`        | simbolo, solo in Adesso    | 30   | Neve                         |
| `sky.alt`         | testo alternativo completo | riga | {cielo}. Pioggia: {modelli}. |

## Nuvole del bollettino METAR

The highest cloud cover the airport reports. It is what the airport sees, so it is shown as such.

| chiave              | dove   | max | testo              |
| ------------------- | ------ | --- | ------------------ |
| `metar.cover.CAVOK` | Adesso | 24  | Sereno o quasi     |
| `metar.cover.NSC`   | Adesso | 24  | Sereno o quasi     |
| `metar.cover.NCD`   | Adesso | 24  | Sereno o quasi     |
| `metar.cover.SKC`   | Adesso | 24  | Sereno             |
| `metar.cover.CLR`   | Adesso | 24  | Sereno             |
| `metar.cover.FEW`   | Adesso | 24  | Poche nuvole       |
| `metar.cover.SCT`   | Adesso | 24  | Poco nuvoloso      |
| `metar.cover.BKN`   | Adesso | 24  | Nuvoloso           |
| `metar.cover.OVC`   | Adesso | 24  | Coperto            |
| `metar.cover.VV`    | Adesso | 24  | Cielo non visibile |

## Fenomeni del bollettino METAR

The code reads each group of the METAR weather field (for example `-RA BR`) and writes the parts below in order: intensity, kind, phenomenon. `-RA BR` becomes "Pioggia debole, foschia". Unknown codes show as "Fenomeno non riconosciuto ({codice})".

| chiave        | dove                                                                     | max | testo                                |
| ------------- | ------------------------------------------------------------------------ | --- | ------------------------------------ |
| `wx.light`    | intensità `-`                                                            | 12  | debole                               |
| `wx.heavy`    | intensità `+`                                                            | 12  | forte                                |
| `wx.light_pl` | intensità `-` dopo rovesci                                               | 12  | deboli                               |
| `wx.heavy_pl` | intensità `+` dopo rovesci                                               | 12  | forti                                |
| `wx.vicinity` | `VC`                                                                     | 24  | nelle vicinanze                      |
| `wx.SH`       | rovesci, seguito dal fenomeno                                            | 16  | rovesci di                           |
| `wx.SH_alone` | rovesci senza fenomeno indicato (VCSH diventa "Rovesci nelle vicinanze") | 16  | rovesci                              |
| `wx.TS`       | temporale                                                                | 16  | temporale                            |
| `wx.TS_with`  | temporale con un fenomeno                                                | 20  | temporale con                        |
| `wx.FZ`       | che gela                                                                 | 16  | che gela                             |
| `wx.MI`       | sottile                                                                  | 12  | sottile                              |
| `wx.BC`       | a banchi                                                                 | 12  | a banchi                             |
| `wx.PR`       | parziale                                                                 | 12  | parziale                             |
| `wx.BL`       | sollevata dal vento                                                      | 24  | sollevata dal vento                  |
| `wx.DR`       | trasportata dal vento                                                    | 24  | trasportata dal vento                |
| `wx.RA`       | fenomeno                                                                 | 20  | pioggia                              |
| `wx.DZ`       | fenomeno                                                                 | 20  | pioviggine                           |
| `wx.SN`       | fenomeno                                                                 | 20  | neve                                 |
| `wx.SG`       | fenomeno                                                                 | 20  | nevischio                            |
| `wx.GR`       | fenomeno                                                                 | 20  | grandine                             |
| `wx.GS`       | fenomeno                                                                 | 20  | grandine piccola                     |
| `wx.PL`       | fenomeno                                                                 | 20  | granuli di ghiaccio                  |
| `wx.UP`       | fenomeno                                                                 | 32  | precipitazione non identificata      |
| `wx.BR`       | fenomeno                                                                 | 20  | foschia                              |
| `wx.FG`       | fenomeno                                                                 | 20  | nebbia                               |
| `wx.HZ`       | fenomeno                                                                 | 20  | caligine                             |
| `wx.FU`       | fenomeno                                                                 | 20  | fumo                                 |
| `wx.DU`       | fenomeno                                                                 | 20  | polvere                              |
| `wx.SA`       | fenomeno                                                                 | 20  | sabbia                               |
| `wx.VA`       | fenomeno                                                                 | 20  | cenere vulcanica                     |
| `wx.unknown`  | codice sconosciuto                                                       | 40  | Fenomeno non riconosciuto ({codice}) |

## Pagine di testo: titoli e link

| chiave               | dove                                   | max  | testo                                 |
| -------------------- | -------------------------------------- | ---- | ------------------------------------- |
| `page.how.title`     | titolo della pagina                    | 40   | Come funziona                         |
| `page.sources.title` | titolo della pagina                    | 40   | Fonti e licenze                       |
| `page.privacy.title` | titolo della pagina                    | 40   | Privacy                               |
| `page.score.title`   | titolo della pagina                    | 40   | Quanto ci prendiamo                   |
| `page.back`          | link per tornare al paese              | 30   | Torna a {paese}                       |
| `page.404.title`     | titolo della pagina 404 e della scheda | 40   | Pagina non trovata                    |
| `page.404.p1`        | prima frase                            | riga | Questo indirizzo non esiste sul sito. |
| `page.404.p2`        | prima dei link ai due paesi            | riga | Le previsioni sono qui:               |
| `page.updated`       | sotto il titolo delle pagine di testo  | 40   | Aggiornato il {data}                  |

## Testi lunghi

Drafts. Each block below is one paragraph or one list item; the owner rewrites them. The facts in them come from the plan and the agreed plan; anything the owner is not sure of should go.

#### page.how.intro

Questo sito fa le previsioni per due paesi, Pedrengo e Sesto Calende. Non inventa un modello nuovo: prende quelli che esistono, corregge i loro errori abituali e lo dice quando non è sicuro.

#### page.how.h_station

Perché una stazione

#### page.how.station

Né Pedrengo né Sesto Calende hanno una stazione meteo. La previsione è fatta per la stazione ARPA Lombardia più adatta: Torre Boldone per Pedrengo, Ispra JRC per Sesto Calende. Il sito scrive sempre quale stazione usa e a che distanza è. Anche due stazioni vicine non misurano lo stesso: Torre Boldone e Bergamo, a meno di 2 km, differiscono in media di più di mezzo grado, e di notte Varano Borghi è in media 2,6 °C più freddo di Ispra.

#### page.how.h_models

Da dove viene la previsione

#### page.how.models

Ogni ora controlliamo se sono uscite nuove corse di dieci modelli meteorologici, scaricati da Open-Meteo: ECMWF IFS e AIFS, ICON-D2 e ICON-EU del servizio tedesco, ICON-2I del servizio italiano, ICON-CH1 e ICON-CH2 del servizio svizzero, AROME del servizio francese, il modello globale del servizio britannico e GFS del servizio americano. Alcuni arrivano a 2 giorni, altri a 10 o più: per questo più si guarda lontano, meno modelli ci sono.

#### page.how.h_correction

La correzione

#### page.how.correction

Ogni modello sbaglia a modo suo: c'è chi fa troppo caldo di notte e chi troppo freddo di giorno. Per ogni modello calcoliamo l'errore medio degli ultimi 60 giorni rispetto alla stazione, separato per ora del giorno e per giorno di anticipo, e lo togliamo. Poi facciamo la media dei modelli corretti, tutti con lo stesso peso. Un modello entra nella media solo se ha almeno 45 giorni di confronti su 60. I coefficienti si ricalcolano ogni notte.

#### page.how.h_what

Cosa è corretto e cosa no

#### page.how.what

In questa versione correggiamo solo la temperatura: quella ora per ora, la massima e la minima, ognuna con la sua correzione. Vento, raffiche, nuvole, punto di rugiada e quantità di pioggia sono la media semplice dei modelli, senza correzione, e il sito lo scrive accanto a ogni valore.

#### page.how.h_range

L'intervallo tra i modelli

#### page.how.range

Accanto alla temperatura mostriamo il valore più basso e quello più alto tra i modelli corretti. Non è una probabilità: dice solo quanto i modelli sono d'accordo tra loro. Se la fascia è stretta, i modelli si somigliano; se è larga, c'è più incertezza. Anche quando sono tutti d'accordo possono sbagliare insieme.

#### page.how.h_rain

La pioggia

#### page.how.rain

Per ogni ora contiamo quanti modelli danno almeno 0,2 mm, per ogni giorno quanti ne danno almeno 1 mm. "7 modelli su 10" vuol dire questo, e non una probabilità del 70%. La quantità che vedi nella tabella è la media dei modelli, senza correzione. Una vera probabilità di pioggia, misurata e calibrata, arriverà con la versione 1.0.

#### page.how.h_symbols

I simboli

#### page.how.symbols

Il simbolo del cielo viene dalle nuvole previste e da quanti modelli danno pioggia. Una goccia vuota vuol dire pioggia possibile: la dà qualche modello, ma meno della metà. Le gocce piene compaiono quando la dà almeno la metà dei modelli, e sono una, due o tre secondo la quantità media. Nebbia, temporale e neve compaiono solo in Adesso, perché vengono dal bollettino dell'aeroporto.

#### page.how.h_far

Giorni 8, 9 e 10

#### page.how.far

Così lontano arrivano di solito solo tre modelli, e la correzione usata è quella del settimo giorno. Per questo li segniamo come meno affidabili.

#### page.how.h_now

Adesso

#### page.how.now

I valori di Adesso sono misurati, non previsti. Vengono dai bollettini METAR degli aeroporti di Orio al Serio, per Pedrengo, e di Malpensa, per Sesto Calende, che escono ogni 30 minuti, e dal radar della Protezione Civile, che fa un'immagine ogni 5 minuti. L'aeroporto non è in paese: per questo scriviamo sempre a quanti chilometri si trova e quanti minuti ha il dato.

#### page.how.h_times

Orari

#### page.how.times

Tutti gli orari sono quelli italiani. La notte del 25 ottobre 2026 torna l'ora solare: alle 3 si torna alle 2, e nel grafico e nella tabella le ore dalle 2 alle 3 compaiono due volte.

#### page.how.h_score

Quanto ci prendiamo

#### page.how.score

Da fine novembre pubblicheremo l'errore delle nostre previsioni rispetto alle stazioni, con il numero di casi e il periodo, anche quando i modelli senza correzione fanno meglio di noi.

#### page.sources.intro

Il sito usa solo dati aperti. Qui sotto ci sono tutte le fonti, cosa ne facciamo e con quale licenza.

#### page.sources.openmeteo

Previsioni dei modelli: Open-Meteo.com, licenza CC BY 4.0. I modelli sono dei servizi meteorologici europei, americano e britannico elencati in Come funziona.

#### page.sources.radar

Radar: Dipartimento della Protezione Civile (Radar-DPC), licenza CC BY-SA 4.0. Per questo anche le immagini del radar che pubblichiamo sono CC BY-SA 4.0.

#### page.sources.metar

Bollettini degli aeroporti (METAR) di Orio al Serio e Malpensa: dati pubblici, scaricati dall'Aviation Weather Center della NOAA.

#### page.sources.arpa

Stazioni di Torre Boldone, Ispra JRC e Varano Borghi: ARPA Lombardia, licenza CC0. Servono a correggere e verificare le previsioni.

#### page.sources.map

Mappa sotto il radar: Natural Earth, di pubblico dominio.

#### page.sources.symbols

Simboli del cielo: disegnati per questo sito, con la stessa licenza del codice.

#### page.sources.ours

Le previsioni che pubblichiamo hanno licenza CC BY-SA 4.0. Il codice del sito e della pipeline ha licenza MIT.

#### page.privacy.p1

Questo sito non usa cookie e non raccoglie dati personali. Non ci sono statistiche di visita, pubblicità, caratteri o servizi di altri siti.

#### page.privacy.p2

Il paese che scegli resta salvato solo nel tuo browser, per riaprirlo la volta dopo. Non lo riceviamo noi. Puoi cancellarlo dalle impostazioni del browser, alla voce dei dati dei siti.

#### page.privacy.p3

Le pagine del sito sono file fissi, distribuiti dalla rete di Microsoft Azure Static Web Apps; le impostazioni del servizio stanno in una regione Azure negli Stati Uniti (East US 2). I dati meteo arrivano da un archivio Azure in Italia. Come ogni server web, quelli di Azure ricevono l'indirizzo IP di chi si collega. Il sito non ha un server suo, non registra le visite e non conserva niente su chi lo usa.

#### page.score.p1

Questa pagina arriva con la versione 0.2, prevista per fine novembre 2026.

#### page.score.p2

Per ogni paese e per ogni giorno di anticipo pubblicheremo l'errore medio della temperatura, con il numero di casi, il periodo e un intervallo di confidenza, e quanto spesso la pioggia era giusta. Lo confronteremo con i modelli senza correzione e con altri servizi, compresi i casi in cui facciamo peggio.

#### page.score.p3

Le previsioni che il sito emette sono archiviate dal 17 ottobre 2026 e non si possono modificare dopo.
