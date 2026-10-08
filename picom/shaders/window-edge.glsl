#version 330
in vec2 texcoord;
uniform sampler2D tex;
uniform float corner_radius;
vec4 default_post_processing(vec4 color);

vec4 window_shader() {
    vec2 size = vec2(textureSize(tex, 0));
    vec4 color = default_post_processing(texelFetch(tex, ivec2(texcoord), 0));
    float radius = min(14.0, min(size.x, size.y) / 2.0);
    vec2 edge = min(texcoord, size - texcoord);
    // Tab headers own the top corners; this frame owns the bottom ones.
    if (corner_radius == 0.0) {
        edge.y = size.y - texcoord.y;
    }
    float distance = length(max(vec2(radius) - edge, vec2(0.0))) - radius;
    vec4 border = default_post_processing(texelFetch(tex, ivec2(0, size.y / 2.0), 0));
    color = mix(color, border, clamp(distance + 2.0, 0.0, 1.0));
    if (corner_radius == 0.0) {
        color *= clamp(1.0 - distance, 0.0, 1.0);
    }
    if (texcoord.x >= size.x - 2.0) {
        color.rgb = vec3(192.0, 175.0, 213.0) / 255.0 * color.a;
    }
    return color;
}
