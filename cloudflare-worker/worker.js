addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
});

offsets = {
  "1.14.3002": {
    "base_offset": 0x03022668,
    "offsets": [
      0xC0,
      0xF80,
      0xB0,
      0xCE8,
      0xB0,
      0x120,
      0xF0
    ]
  },
  "1.14.6005": {
    "base_offset": 0x03059208,
    "offsets": [
        0xC0,
        0x890,
        0xB0,
        0xDD0,
        0xB0,
        0x120,
        0xF0
    ]
  },
  "1.16.2": {
    "base_offset": 0x03858120,
    "offsets": [
        0x18,
        0xC8,
        0x830,
        0x8,
        0x40,
        0x120,
        0xF0
    ]
  },
  "1.16.102": {
    "base_offset": 0x036D94B8,
    "offsets": [
        0xE8,
        0x10,
        0xE38,
        0xB0,
        0x120,
        0xF0
    ]
  }
};

// Needed request version for mc version
neededVersion = {
  "1.14.3002": 100,
  "1.14.6005": 101,
  "1.16.2": 101,
  "1.16.102": 101
};

// old, will get removed
configVersions = ["1.0.0"];

error = "$ERROR$";
paramsAllowed = ["api_key", "token", "config_version", "version", "mc_version"]; // token, config_version will get removed
paramCount = 3;

/*
 * Handle query parameters
 * @param {Request} request
 */
async function getOffset(request) {
  /*
   * Handle parameters
   */
  let params = {};
  var queryString = request.url.split("?", 2);

  // Check if there are queries
  if (queryString.length !== 2) {return [error, "No parameters were given!", 400]}

  queryString = queryString[1].split("&");

  var invalid;
  queryString.forEach(element => {
    let sp = element.split("=", 2);
    // Only allowed params
    if (!paramsAllowed.includes(sp[0])) {invalid = error}
    params[sp[0]] = sp[1];
  });

  if (invalid === error) {return [error, "Invalid parameter!", 400]}

  // How many queries
  if (Object.keys(params).length !== paramCount) {return [error, "Invalid parameter count!", 400]}

  /*
   * Request type
   */

  let resp = await isOldRequest(params);
  if (resp && resp !== error) {
    // Old type of request
    return await oldRequestHandle(params);

  } else if (resp === error) {
    return [error, "Invalid request!", 400]

  }

  /*
   * Authentication
   */
  if (!API_KEYS.split(";").includes(params["api_key"])) {return [error, "Invalid api_key!", 401]}

  /*
   * Get offset
   */
  if (!offsets.hasOwnProperty(params["mc_version"])) {return [error, "Unsupported mc version!", 404]}

  return offsets[params["mc_version"]];
}

async function isOldRequest(params) {
  if (params.hasOwnProperty("token") && params.hasOwnProperty("config_version") && params.hasOwnProperty("mc_version")) {
    return true;

  } else if (params.hasOwnProperty("api_key") && params.hasOwnProperty("version") && params.hasOwnProperty("mc_version")) {
    return false;

  } else {
    return error;
  }
}

async function oldRequestHandle(params) {
  /*
   * Authentication
   */
  if (!API_KEYS.split(";").includes(params["token"])) {return [error, "Invalid api_key!", 401]}

  /*
   * Get offset
   */

  // Config version allowed
  if (!configVersions.includes(params["config_version"])) {return [error, "Invalid config version!", 404]}

  if (!offsets.hasOwnProperty(params["mc_version"])) {return [error, "Unsupported mc version!", 404]}

  return offsets[params["mc_version"]];
}

/**
 * Respond to the request
 * @param {Request} request
 */
async function handleRequest(request) {
  let offset = await getOffset(request);

  if (offset instanceof Array && offset.includes(error)) {
    return new Response(JSON.stringify({status: 400, message: offset[1]}), {status: offset[2], headers: {"Content-Type": "text/json"}})
  } else {
    return new Response(JSON.stringify(offset), {status: 200, headers: {"Content-Type": "text/json"}})
  }
}