# -*- coding: utf-8 -*-
# istSOS. See https://istsos.org/
# License: https://github.com/istSOS/istsos3/master/LICENSE.md
# Version: v3.0.0

import asyncio
import istsos
import uuid
from istsos import setting
from istsos.entity.rest.response import Response
from istsos.actions.action import CompositeAction


class Insert(CompositeAction):
    """
        Regular Time series example body:
        4759a210178a11e6a91c0800273cbaca;
        2017-03-13T14:40:15+0100;PT10M;
        0.2,18.30,69,4.3@0.4,18.80,73,4.1

        Irregular Time series example body:
        4759a210178a11e6a91c0800273cbaca;
        2017-03-13T14:40:15+0100,0.2,18.30,69,4.3@
        2017-03-13T14:40:15+0100,0.4,18.80,73,4.1

        (without line breaks)

        How exception are handled:
        - Wrong sampling time format: no insert
        - Sampling time before end position or after now: no insert
        - Wrong measure value (not a number): is a no data value

    """

    MODE_IRREGULAR = 1
    MODE_REGULAR = 2

    @asyncio.coroutine
    def before(self, request):

        self.data = request.get_rest_data()

        request.set_filter({
            "offerings": [self.data['offering']]
        })

        yield from self.add_retriever('Offerings')

    @asyncio.coroutine
    def after(self, request):

        offering = request['offerings'][0]

        if len(request['offerings'])==0:
            raise Exception(
                "Offering \"%s\" not registered" % self.data['offering'])

        if offering['foi_type'] == setting._SAMPLING_SPECIMEN:
            raise Exception(
                "Offering type \"speciment\" not yet supported")

        if not offering['fixed']:
            raise Exception(
                "Not fixed Offering not yet supported")

        columns = []
        for op in offering['observable_properties']:
            if not op['type'] == setting._COMPLEX_OBSERVATION:
                columns.extend([
                    op['column'],
                    "%s_qi" % op['column']
                ])

        bp = ep = None
        if offering['phenomenon_time'] is not None:
            bp = istsos.str2date(
                offering['phenomenon_time']['timePeriod']['begin']
            )
            ep = istsos.str2date(
                offering['phenomenon_time']['timePeriod']['end']
            )

        obsCnt = 1

        if setting._COMPLEX_OBSERVATION in offering['observation_types']:
            obsCnt = len(offering['observable_properties']) - 1

        dbmanager = yield from self.init_connection()
        cur = dbmanager.cur

        rows = self.data['observations']
        values = []
        for row in rows:
            try:
                sampling_time = row.pop(0)
                sampling_time_dt = istsos.str2date(sampling_time)

            except Exception as dtex:
                raise Exception(
                    "Procedure %s, Sampling time (%s) "
                    "wrong format" % (
                        offering['name'], sampling_time
                    )
                )

            params = [
                str(uuid.uuid1()).replace('-', ''),
                sampling_time,
                sampling_time,
                sampling_time
            ]

            # Check time consistency
            if offering['phenomenon_time'] is not None:
                # If the end position exists the new measures
                # must be after
                if sampling_time_dt < ep:
                    # non blocking exception: skip row
                    istsos.debug("Skipping observation: %s" % row)
                    continue

            if len(row) != obsCnt:
                istsos.debug(
                    "Observations count missmatch (%s!=%s)" % (
                        len(row), obsCnt
                    )
                )
                continue

            params = params + row
            values.append(
                (
                    yield from cur.mogrify(
                        (
                            '(%s, %s, %s, %s, ' +
                            ', '.join(
                                ["%s, 100"] * obsCnt
                            ) + ')'
                        ),
                        tuple(params)
                    )
                ).decode("utf-8")
            )

        if len(values)>0:

            yield from self.begin()

            print(
                (
                    yield from cur.mogrify(
                        ("""
                        INSERT INTO data._%s(
                            obs_id,
                            begin_time,
                            end_time,
                            result_time,
                            %s
                        )
                        """ % (
                            offering['name'].lower(),
                            ", ".join(columns)
                        )) + (
                            " VALUES %s" % ", ".join(values)
                        )
                    )
                ).decode("utf-8")
            )

            yield from cur.execute(
                ("""
                INSERT INTO data._%s(
                    obs_id,
                    begin_time,
                    end_time,
                    result_time,
                    %s
                )
                """ % (
                    offering['name'].lower(),
                    ", ".join(columns)
                )) + (
                    " VALUES %s" % ", ".join(values)
                )
            )

            if offering['phenomenon_time'] is not None:
                yield from cur.execute("""
                    UPDATE public.offerings
                    SET
                        pt_end=%s::TIMESTAMPTZ
                    WHERE id = %s;
                """, (sampling_time, offering['id']))

            else:
                yield from cur.execute("""
                    UPDATE public.offerings
                    SET
                        pt_end=%s::TIMESTAMPTZ,
                        et_end=%s::TIMESTAMPTZ
                    WHERE id = %s;
                """, (sampling_time, sampling_time, offering['id']))

            yield from self.commit()

        request['response'] = Response(
            json_source=Response.get_template()
        )
