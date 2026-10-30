# Spring Boot & Spring Framework

## IoC Container và Dependency Injection
Inversion of Control: thay vì object tự tạo dependency, container (ApplicationContext) tạo và inject vào. Lợi ích: loose coupling, dễ test, dễ thay thế implementation.

Ba kiểu injection: constructor (khuyến dùng — immutable với final, bắt buộc dependency, dễ test, phát hiện circular dependency sớm), setter (optional dependency), field (@Autowired trực tiếp field — khó test, không khuyến khích).

BeanFactory là container cơ bản (lazy). ApplicationContext mở rộng BeanFactory: eager init singleton, hỗ trợ i18n, event publishing, AOP, annotation.

## Bean Scope và Lifecycle
Scope: singleton (mặc định, một instance cho cả container), prototype (mỗi lần request tạo mới), request/session/application (web).

Lifecycle: instantiate → populate properties → BeanNameAware/BeanFactoryAware → @PostConstruct / InitializingBean.afterPropertiesSet → bean sẵn sàng → @PreDestroy / DisposableBean.destroy khi container tắt.

## Stereotype Annotations
@Component: bean chung. @Service: tầng business logic (ngữ nghĩa). @Repository: tầng data access, kèm exception translation (chuyển database exception thành Spring DataAccessException). @Controller / @RestController: tầng web. Tất cả đều được component scan phát hiện.

## Auto-configuration
@SpringBootApplication gộp @Configuration + @EnableAutoConfiguration + @ComponentScan. Auto-configuration dựa trên classpath: nếu có H2 trên classpath, Spring Boot tự cấu hình DataSource. Cơ chế qua spring.factories (Spring Boot 2) hoặc AutoConfiguration.imports (Boot 3), kèm @ConditionalOnClass, @ConditionalOnMissingBean. Có thể override bằng cách định nghĩa bean của chính mình.

## Spring AOP
Aspect-Oriented Programming tách cross-cutting concern (logging, transaction, security) khỏi business logic. Spring AOP dùng proxy: JDK dynamic proxy nếu bean implement interface, CGLIB (subclass) nếu không. Advice: @Before, @After, @Around, @AfterReturning, @AfterThrowing. Pointcut định nghĩa nơi áp dụng.

Giới hạn quan trọng: self-invocation — gọi method trong cùng class không đi qua proxy nên @Transactional/@Cacheable không có hiệu lực. Giải pháp: tách sang bean khác hoặc inject self.

## @Transactional
Dựa trên AOP proxy. Spring begin transaction trước method, commit nếu thành công, rollback nếu gặp RuntimeException (mặc định KHÔNG rollback với checked exception — dùng rollbackFor để đổi).

Propagation: REQUIRED (mặc định, tham gia tx hiện có hoặc tạo mới), REQUIRES_NEW (luôn tạo tx mới, tạm dừng tx cũ), SUPPORTS, MANDATORY, NESTED. Isolation: READ_COMMITTED, REPEATABLE_READ, SERIALIZABLE — kiểm soát dirty read, non-repeatable read, phantom read.

## Spring MVC request flow
Request → DispatcherServlet → HandlerMapping tìm controller → HandlerAdapter gọi method → trả về ModelAndView hoặc @ResponseBody (JSON qua HttpMessageConverter) → ViewResolver (nếu cần) → response. @RequestMapping/@GetMapping/@PostMapping ánh xạ URL. @RequestBody deserialize JSON, @PathVariable, @RequestParam.

## Spring Data JPA
Repository interface (JpaRepository) tự sinh query từ tên method (findByEmailAndStatus). @Query cho JPQL/native. Lưu ý N+1 problem: lazy loading trong vòng lặp gây nhiều query — giải quyết bằng JOIN FETCH hoặc @EntityGraph. Pagination qua Pageable.

## Cấu hình và Profile
application.yml / application.properties. @Value inject giá trị, @ConfigurationProperties bind nhóm property vào POJO. Profile (@Profile, spring.profiles.active) tách cấu hình theo môi trường (dev, prod). Externalized config ưu tiên: command-line > env var > application-{profile}.yml > application.yml.

## Spring Boot Actuator
Cung cấp endpoint giám sát: /health, /metrics, /info, /env. Tích hợp Micrometer để export metrics sang Prometheus. Quan trọng cho observability trong production.
