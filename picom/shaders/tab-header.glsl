#version 330
in vec2 texcoord;
uniform sampler2D tex;
vec4 default_post_processing(vec4 color);

vec4 window_shader() {
    vec2 size = vec2(textureSize(tex, 0));
    vec4 color = default_post_processing(texelFetch(tex, ivec2(texcoord), 0));
    float radius = min(14.0, min(size.x, size.y) / 2.0);
    vec2 edge = vec2(min(texcoord.x, size.x - texcoord.x), texcoord.y);
    float distance = length(max(vec2(radius) - edge, vec2(0.0))) - radius;
    color *= clamp(1.0 - distance, 0.0, 1.0);
    if (texcoord.x >= size.x - 2.0) {
        color.rgb = vec3(192.0, 175.0, 213.0) / 255.0 * color.a;
    }
    return color;
}
