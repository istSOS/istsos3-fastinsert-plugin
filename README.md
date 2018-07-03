# Fast Insert plugin for istSOS3

This is a porting from the old istSOS2 fast insert feature

## Usage

Classic istSOS3 action request:

```json
{
    "action": "FASTINSERT",
    "data": {
    	"offering": "test_002",
    	"observations": [
    		["2017-03-13T14:40:00+0100", 1, 2, 3, 4, 5, 6, 7, 8, 9]
    	]
    }
}
```

Or posting a plain text body (only with modification to tornado web):

```
test_002;2017-03-13T17:00:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T17:10:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T17:20:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T17:30:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T17:40:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T17:50:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T18:00:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T18:10:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T18:20:00+0100,1,2,3,4,5,6,7,8,9@2017-03-13T18:30:00+0100,1,2,3,4,5,6,7,8,9
```


## Installation

Add the plugin to your istSOS3 instance by doing this:

```bash
git clone https://gitlab.com/ist-supsi/istsos3-fastinsert-plugin.git
cd istsos3-fastinsert-plugin
ls -l fastinsert /path_to_istsos3/istsos/plugin/
```

To mimic the istSOS2 implementation a small modification shall be made to the
tornado example.

Add this class:

```python
class FastInsertHandler(BaseHandler):

    MODE_IRREGULAR = 1
    MODE_REGULAR = 2

    @coroutine
    def post(self, *args, **kwargs):

        self.set_header("Content-Type", "application/json; charset=utf-8")

        try:
            data = self.request.body.decode('utf-8').split(";")
            action = {
                "action": "FASTINSERT",
                "data": {
                    "offering": data[0],
                    "observations": []
                }
            }
            data = data[1].split("@")
            for i in range(0, len(data)):
                action['data']['observations'].append(
                    data[i].split(",")
                )
            request = HttpRequest(
                "POST",
                'rest',
                body=self.request.body.decode('utf-8'),
                json=action,
                content_type='application/json; charset=utf-8'
            )
            yield from self.istsos.execute_http_request(
                request, stats=True
            )
            self.write(request['response'])

        except Exception as ex:
            self.write({
                "success": False,
                "message": str(ex)
            })
```

And configure the tornado Application configuring the handlers, like this:


```python
app = Application([
    (r'/sos', SosHandler),
    (r'/rest', RestHandler),
    (r'/fastinsert', FastInsertHandler)
], **settings)

```
