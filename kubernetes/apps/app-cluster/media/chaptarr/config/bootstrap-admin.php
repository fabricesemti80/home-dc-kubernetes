<?php

function hostConfig(string $apiKey, ?array $settings = null): ?array
{
    $url = 'http://127.0.0.1:8789/api/v1/config/host';
    $request = curl_init($settings === null ? $url : "$url/1");
    curl_setopt_array($request, [
        CURLOPT_HTTPHEADER => ["X-Api-Key: $apiKey", 'Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_PROXY => '',
        CURLOPT_TIMEOUT => 4,
    ]);
    if ($settings !== null) {
        curl_setopt($request, CURLOPT_CUSTOMREQUEST, 'PUT');
        curl_setopt($request, CURLOPT_POSTFIELDS, json_encode($settings, JSON_THROW_ON_ERROR));
    }
    $body = curl_exec($request);
    return curl_getinfo($request, CURLINFO_RESPONSE_CODE) === 200 && is_string($body)
        ? json_decode($body, true, 512, JSON_THROW_ON_ERROR)
        : null;
}

function credential(string $key): string
{
    $value = @file_get_contents("/run/admin-credentials/$key");
    if ($value === false || trim($value) === '') {
        throw new RuntimeException('Missing admin credential');
    }
    return $value;
}

try {
    // Chaptarr generates the API key on first boot and rotates it when authentication is enabled.
    for ($attempt = 0; $attempt < 90; $attempt++) {
        $config = @simplexml_load_file('/config/config.xml', SimpleXMLElement::class, LIBXML_NONET);
        $apiKey = $config === false ? '' : (string) $config->ApiKey;
        $settings = $apiKey === '' ? null : hostConfig($apiKey);
        if ($settings !== null) {
            if (($settings['username'] ?? '') !== '') {
                exit(0);
            }
            $settings['authenticationMethod'] = 'forms';
            $settings['authenticationRequired'] = 'enabled';
            $settings['username'] = credential('CHAPTARR_ADMIN_USERNAME');
            $settings['password'] = credential('CHAPTARR_ADMIN_PASSWORD');
            $settings['passwordConfirmation'] = $settings['password'];
            if ((hostConfig($apiKey, $settings)['username'] ?? '') !== $settings['username']) {
                throw new RuntimeException('Admin setup rejected');
            }
            exit(0);
        }
        sleep(2);
    }
} catch (Throwable $error) {
    // Never write credentials, API keys, request payloads or response bodies to pod events.
    fwrite(STDERR, "Chaptarr admin bootstrap failed; check Doppler keys and the host configuration.\n");
    exit(1);
}
fwrite(STDERR, "Timed out waiting for the Chaptarr host configuration API.\n");
exit(1);
